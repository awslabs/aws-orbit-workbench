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
from typing import List, cast

import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_iam as iam
import aws_cdk.aws_ssm as ssm
from aws_cdk.core import App, CfnOutput, Construct, Duration, Environment, IConstruct, Stack, Tags

from datamaker_cli.manifest import Manifest, SubnetKind
from datamaker_cli.utils import extract_images_names, path_from_filename

_logger: logging.Logger = logging.getLogger(__name__)


class Env(Stack):
    def __init__(
        self, scope: Construct, id: str, manifest: Manifest, add_images: List[str], remove_images: List[str]
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
        Tags.of(scope=self).add(key="Env", value=f"datamaker-{self.manifest.name}")
        self.i_vpc = ec2.Vpc.from_vpc_attributes(
            scope=self,
            id="vpc",
            vpc_id=self.manifest.vpc.vpc_id,
            availability_zones=self.manifest.vpc.availability_zones,
        )
        self.i_private_subnets = self._initialize_private_subnets()
        self.i_public_subnets = self._initialize_public_subnets()
        self.repos = self._create_ecr_repos()
        self.role_eks_cluster = self._create_role_cluster()
        self.role_eks_env_nodegroup = self._create_env_nodegroup_role()
        self.user_pool = self._create_user_pool()
        self.user_pool_client = self._create_user_pool_client()
        self.identity_pool = self._create_identity_pool()
        self.manifest_parameter = self._create_manifest_parameter()

    def _initialize_private_subnets(self) -> List[ec2.ISubnet]:
        return [
            ec2.PrivateSubnet.from_subnet_attributes(
                scope=self,
                id=s.subnet_id,
                subnet_id=s.subnet_id,
                availability_zone=s.availability_zone,
                route_table_id=s.route_table_id,
            )
            for s in self.manifest.vpc.subnets
            if s.kind == SubnetKind.private
        ]

    def _initialize_public_subnets(self) -> List[ec2.ISubnet]:
        return [
            ec2.PublicSubnet.from_subnet_attributes(
                scope=self,
                id=s.subnet_id,
                subnet_id=s.subnet_id,
                availability_zone=s.availability_zone,
                route_table_id=s.route_table_id,
            )
            for s in self.manifest.vpc.subnets
            if s.kind == SubnetKind.public
        ]

    def create_repo(self, image_name: str) -> ecr.Repository:
        repo = ecr.Repository(
            scope=self, id=f"repo-{image_name}", repository_name=f"datamaker-{self.manifest.name}-{image_name}"
        )
        Tags.of(scope=repo).add(key="Env", value=f"datamaker-{self.manifest.name}")
        return repo

    def _create_ecr_repos(self) -> List[ecr.Repository]:
        current_images_names = extract_images_names(env_name=self.manifest.name)
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
                export_name=f"datamaker-{self.manifest.name}-repos",
                value=",".join([x for x in current_images_names]),
            )
        return repos

    def _create_role_cluster(self) -> iam.Role:
        name: str = f"datamaker-{self.manifest.name}-eks-cluster-role"
        role = iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("eks.amazonaws.com"),
                iam.ServicePrincipal("eks-fargate-pods.amazonaws.com")
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSClusterPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSServicePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSVPCResourceController")
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
                                "iam:ListAttachedRolePolicies"
                            ],
                            resources=["*"],
                        )
                    ]
                )
            },
        )
        Tags.of(scope=role).add(key="Env", value=f"datamaker-{self.manifest.name}")
        return role

    def _create_env_nodegroup_role(self) -> iam.Role:
        name: str = f"datamaker-{self.manifest.name}-eks-nodegroup-role"
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
        Tags.of(scope=role).add(key="Env", value=f"datamaker-{self.manifest.name}")
        return role

    def _create_user_pool(self) -> cognito.UserPool:
        pool = cognito.UserPool(
            scope=self,
            id="user-pool",
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            auto_verify=cognito.AutoVerifiedAttrs(email=True, phone=False),
            custom_attributes=None,
            email_settings=None,
            lambda_triggers=None,
            mfa=cognito.Mfa.OFF,
            mfa_second_factor=None,
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_digits=True,
                require_lowercase=True,
                require_symbols=True,
                require_uppercase=True,
                temp_password_validity=Duration.days(5),
            ),
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True, phone=False, preferred_username=False, username=True),
            sign_in_case_sensitive=True,
            sms_role=None,
            sms_role_external_id=None,
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            user_invitation=cognito.UserInvitationConfig(
                email_subject="Invite to join DataMaker!",
                email_body="Hello, you have been invited to join DataMaker!<br/><br/>"
                "Username: {username}<br/>"
                "Temporary password: {####}<br/><br/>"
                "Regards",
            ),
            user_pool_name=self.id,
        )
        Tags.of(scope=cast(IConstruct, pool)).add(key="Env", value=f"datamaker-{self.manifest.name}")
        return pool

    def _create_user_pool_client(self) -> cognito.UserPoolClient:
        return cognito.UserPoolClient(
            scope=self,
            id="user-pool-client",
            user_pool=cast(cognito.IUserPool, self.user_pool),
            auth_flows=cognito.AuthFlow(user_srp=True, admin_user_password=False, custom=False),
            generate_secret=False,
            prevent_user_existence_errors=True,
            user_pool_client_name="datamaker",
        )

    def _create_identity_pool(self) -> cognito.CfnIdentityPool:
        pool = cognito.CfnIdentityPool(
            scope=self,
            id="identity-pool",
            identity_pool_name=self.id.replace("-", "_"),
            allow_unauthenticated_identities=False,
            allow_classic_flow=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    provider_name=self.user_pool.user_pool_provider_name,
                    client_id=self.user_pool_client.user_pool_client_id,
                )
            ],
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
                            actions=["mobileanalytics:PutEvents", "cognito-sync:*", "cognito-identity:*"],
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
                                f"parameter/datamaker/{self.manifest.name}/teams/*"
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
            roles={"authenticated": authenticated_role.role_arn, "unauthenticated": unauthenticated_role.role_arn},
        )
        return pool

    def _create_manifest_parameter(self) -> ssm.StringParameter:
        self.manifest.eks_cluster_role_arn = self.role_eks_cluster.role_arn
        self.manifest.eks_env_nodegroup_role_arn = self.role_eks_env_nodegroup.role_arn
        self.manifest.user_pool_id = self.user_pool.user_pool_id
        self.manifest.user_pool_client_id = self.user_pool_client.user_pool_client_id
        self.manifest.identity_pool_id = self.identity_pool.ref

        parameter: ssm.StringParameter = ssm.StringParameter(
            scope=self,
            id=self.manifest.ssm_parameter_name,
            string_value=self.manifest.repr_full_as_string(),
            type=ssm.ParameterType.STRING,
            description="DataMaker Remote Manifest.",
            parameter_name=self.manifest.ssm_parameter_name,
            simple_name=False,
        )
        return parameter


def synth(stack_name: str, filename: str, manifest: Manifest, add_images: List[str], remove_images: List[str]) -> str:
    filename_dir = path_from_filename(filename=filename)
    outdir = os.path.join(filename_dir, ".datamaker.out", manifest.name, "cdk", stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)
    output_filename = os.path.join(outdir, f"{stack_name}.template.json")

    app = App(outdir=outdir)
    Env(scope=app, id=stack_name, manifest=manifest, add_images=add_images, remove_images=remove_images)
    app.synth(force=True)
    return output_filename
