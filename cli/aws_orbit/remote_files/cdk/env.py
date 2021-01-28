#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import logging
import os
import shutil
import sys
from typing import List, cast

import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda_python as lambda_python
import aws_cdk.aws_ssm as ssm
from aws_cdk import aws_lambda
from aws_cdk.core import App, CfnOutput, Construct, Duration, Environment, Stack, Tags
from aws_orbit.manifest import Manifest
from aws_orbit.remote_files.cdk import _lambda_path
from aws_orbit.services import cognito as orbit_cognito
from aws_orbit.utils import extract_images_names

_logger: logging.Logger = logging.getLogger(__name__)


class Env(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        manifest: Manifest,
        add_images: List[str],
        remove_images: List[str],
    ) -> None:
        self.scope = scope
        self.id = id
        self.manifest = manifest
        self.add_images = add_images
        self.remove_images = remove_images
        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=self.manifest.account_id, region=self.manifest.region),
        )
        Tags.of(scope=self).add(key="Env", value=f"orbit-{self.manifest.name}")
        self.i_vpc = ec2.Vpc.from_vpc_attributes(
            scope=self,
            id="vpc",
            vpc_id=self.manifest.vpc.vpc_id,
            availability_zones=self.manifest.vpc.availability_zones,
        )
        self.repos = self._create_ecr_repos()
        self.role_eks_cluster = self._create_role_cluster()
        self.role_eks_env_nodegroup = self._create_env_nodegroup_role()
        self.role_fargate_profile = self._create_role_fargate_profile()
        if hasattr(self.manifest, "user_pool_id") and self.manifest.user_pool_id:
            self.manifest.cognito_users_urls = orbit_cognito.get_users_url(
                user_pool_id=self.manifest.user_pool_id, region=self.manifest.region
            )
            cognito_pool_arn: str = orbit_cognito.get_pool_arn(
                user_pool_id=self.manifest.user_pool_id, region=self.manifest.region, account=self.manifest.account_id
            )
            self.user_pool: cognito.UserPool = self._get_user_pool(user_pool_arn=cognito_pool_arn)
        else:
            raise Exception("Missing Cognito User Pool ID ('user_pool_id') ")
        self.user_pool_client = self._create_user_pool_client()
        self.identity_pool = self._create_identity_pool()
        self.token_validation_lambda = self._create_token_validation_lambda()
        self.manifest_parameter = self._create_manifest_parameter()

    def create_repo(self, image_name: str) -> ecr.Repository:
        return ecr.Repository(
            scope=self,
            id=f"repo-{image_name}",
            repository_name=f"orbit-{self.manifest.name}-{image_name}",
        )

    def _create_ecr_repos(self) -> List[ecr.Repository]:
        current_images_names = extract_images_names(manifest=self.manifest)
        current_images_names = list(set(current_images_names) - set(self.remove_images))
        repos = [self.create_repo(image_name=r) for r in current_images_names]
        for image_name in self.add_images:
            if image_name not in current_images_names:
                repos.append(self.create_repo(image_name=image_name))
                current_images_names.append(image_name)
        if current_images_names:
            current_images_names.sort()
            CfnOutput(
                scope=self,
                id="repos",
                export_name=f"orbit-{self.manifest.name}-repos",
                value=",".join([x for x in current_images_names]),
            )
        return repos

    def _create_role_cluster(self) -> iam.Role:
        name: str = f"orbit-{self.manifest.name}-eks-cluster-role"
        role = iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("eks.amazonaws.com"),
                iam.ServicePrincipal("eks-fargate-pods.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSClusterPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSServicePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSVPCResourceController"),
            ],
            inline_policies={
                "Extras": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "elasticloadbalancing:*",
                                "ec2:CreateSecurityGroup",
                                "ec2:Describe*",
                                "cloudwatch:PutMetricData",
                                "iam:ListAttachedRolePolicies",
                            ],
                            resources=["*"],
                        ),
                        # FIXME can this be moved to a service role and only be allowed to access the
                        #  team key after chamcca@ changes
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "kms:CreateGrant",
                                "kms:ListGrants",
                                "kms:RevokeGrant",
                                "kms:DescribeKey",
                                "kms:Encrypt",
                                "kms:Decrypt",
                                "kms:ReEncrypt*",
                                "kms:GenerateDataKey*",
                                "kms:DescribeKey",
                            ],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )
        return role

    def _create_role_fargate_profile(self) -> iam.Role:
        name: str = f"orbit-{self.manifest.name}-eks-fargate-profile-role"
        return iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("eks.amazonaws.com"),
                iam.ServicePrincipal("eks-fargate-pods.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="AmazonEC2ContainerRegistryReadOnly"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="AmazonEKSFargatePodExecutionRolePolicy"
                ),
            ],
            inline_policies={
                "Logging": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:CreateLogStream",
                                "logs:CreateLogGroup",
                                "logs:DescribeLogStreams",
                                "logs:PutLogEvents",
                            ],
                            resources=["*"],
                        )
                    ]
                )
            },
        )

    def _create_env_nodegroup_role(self) -> iam.Role:
        name: str = f"orbit-{self.manifest.name}-eks-nodegroup-role"
        role = iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=cast(iam.IPrincipal, iam.ServicePrincipal(service="ec2.amazonaws.com")),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSWorkerNodePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKS_CNI_Policy"),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    managed_policy_name="AmazonEC2ContainerRegistryReadOnly"
                ),
            ],
        )
        return role

    def _get_user_pool(self, user_pool_arn: str) -> cognito.UserPool:
        return cast(
            cognito.UserPool,
            cognito.UserPool.from_user_pool_arn(scope=self, id="orbit-user-pool", user_pool_arn=user_pool_arn),
        )

    def _create_user_pool_client(self) -> cognito.UserPoolClient:
        return cognito.UserPoolClient(
            scope=self,
            id="user-pool-client",
            user_pool=self.user_pool,
            auth_flows=cognito.AuthFlow(user_srp=True, admin_user_password=False, custom=False),
            generate_secret=False,
            prevent_user_existence_errors=True,
            user_pool_client_name="orbit",
        )

    def _create_identity_pool(self) -> cognito.CfnIdentityPool:
        pool = cognito.CfnIdentityPool(
            scope=self,
            id="identity-pool",
            identity_pool_name=self.id.replace("-", "_"),
            allow_unauthenticated_identities=False,
            allow_classic_flow=False,
            cognito_identity_providers= [ cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    provider_name=self.user_pool.user_pool_provider_name,
                    client_id=self.user_pool_client.user_pool_client_id,
                )] if hasattr(self.user_pool,"user_pool_provider_name") else None
        ,
        )
        name = f"{self.id}-cognito-authenticated-identity-role"
        authenticated_role = iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=iam.FederatedPrincipal(
                federated="cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {"cognito-identity.amazonaws.com:aud": pool.ref},
                    "ForAnyValue:StringLike": {"cognito-identity.amazonaws.com:amr": "authenticated"},
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            inline_policies={
                "cognito-default": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "mobileanalytics:PutEvents",
                                "cognito-sync:*",
                                "cognito-identity:*",
                            ],
                            resources=["*"],
                        )
                    ]
                ),
                "team-context-parameter": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["ssm:DescribeParameters", "ssm:GetParameters"],
                            resources=[
                                f"arn:aws:ssm:{self.manifest.region}:{self.manifest.account_id}:"
                                f"parameter/orbit/{self.manifest.name}/teams/*"
                            ],
                        )
                    ]
                ),
            },
        )
        name = f"{self.id}-cognito-unauthenticated-identity-role"
        unauthenticated_role = iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=iam.FederatedPrincipal(
                federated="cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {"cognito-identity.amazonaws.com:aud": pool.ref},
                    "ForAnyValue:StringLike": {"cognito-identity.amazonaws.com:amr": "unauthenticated"},
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            inline_policies={
                "cognito-default": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "mobileanalytics:PutEvents",
                                "cognito-sync:*",
                            ],
                            resources=["*"],
                        )
                    ]
                )
            },
        )
        cognito.CfnIdentityPoolRoleAttachment(
            scope=self,
            id=f"{self.id}-role-attachment",
            identity_pool_id=pool.ref,
            roles={
                "authenticated": authenticated_role.role_arn,
                "unauthenticated": unauthenticated_role.role_arn,
            },
        )
        return pool

    def _create_token_validation_lambda(self) -> aws_lambda.Function:

        return lambda_python.PythonFunction(
            scope=self,
            id="token_validation_lambda",
            function_name=f"orbit-{self.manifest.name}-token-validation",
            entry=_lambda_path("token_validation"),
            index="index.py",
            handler="handler",
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            timeout=Duration.seconds(5),
            environment={
                "COGNITO_USER_POOL_ID": self.user_pool.user_pool_id,
                "REGION": self.manifest.region,
                "COGNITO_USER_POOL_CLIENT_ID": self.user_pool_client.user_pool_client_id,
            },
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:Describe*", "logs:Create*", "logs:PutLogEvents", "logs:Describe*"],
                    resources=["*"],
                )
            ],
        )

    def _create_manifest_parameter(self) -> ssm.StringParameter:
        self.manifest.eks_cluster_role_arn = self.role_eks_cluster.role_arn
        self.manifest.eks_fargate_profile_role_arn = self.role_fargate_profile.role_arn
        self.manifest.eks_env_nodegroup_role_arn = self.role_eks_env_nodegroup.role_arn
        self.manifest.user_pool_id = self.user_pool.user_pool_id
        self.manifest.user_pool_client_id = self.user_pool_client.user_pool_client_id
        self.manifest.identity_pool_id = self.identity_pool.ref
        manifest_json: str = self.manifest.asjson()
        parameter: ssm.StringParameter = ssm.StringParameter(
            scope=self,
            id=self.manifest.ssm_parameter_name,
            string_value=manifest_json,
            type=ssm.ParameterType.STRING,
            description="Orbit Workbench Remote Manifest.",
            parameter_name=self.manifest.ssm_parameter_name,
            simple_name=False,
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        )
        return parameter


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 5:
        manifest: Manifest
        if sys.argv[1] == "manifest":
            filename = sys.argv[2]
            manifest = Manifest(filename=filename, env=None, region=None)
        elif sys.argv[1] == "env":
            env = sys.argv[2]
            manifest = Manifest(filename=None, env=env, region=None)
        else:
            raise ValueError(f"Unexpected argv[1] ({len(sys.argv)}) - {sys.argv}.")
        add_images = [] if sys.argv[3] == "null" else sys.argv[3].split(sep=",")
        remove_images = [] if sys.argv[4] == "null" else sys.argv[3].split(sep=",")
    else:
        raise ValueError(f"Unexpected number of values in sys.argv ({len(sys.argv)}), {sys.argv}")

    manifest.fillup()

    outdir = os.path.join(".orbit.out", manifest.name, "cdk", manifest.env_stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    app = App(outdir=outdir)
    Env(
        scope=app,
        id=manifest.env_stack_name,
        manifest=manifest,
        add_images=add_images,
        remove_images=remove_images,
    )
    app.synth(force=True)


if __name__ == "__main__":
    main()
