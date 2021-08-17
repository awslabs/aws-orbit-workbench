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

import json
import logging
import os
import shutil
import sys
from typing import cast

import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda_python as lambda_python
import aws_cdk.aws_sam as sam
import aws_cdk.aws_ssm as ssm
from aws_cdk import aws_lambda
from aws_cdk.core import App, Construct, Duration, Environment, IConstruct, Stack, Tags

from aws_orbit.models.context import Context, ContextSerDe
from aws_orbit.remote_files.cdk import _lambda_path
from aws_orbit.remote_files.cdk.team_builders.codeartifact import DeployCodeArtifact
from aws_orbit.services import cognito as orbit_cognito

_logger: logging.Logger = logging.getLogger(__name__)


class Env(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        context: "Context",
    ) -> None:
        self.scope = scope
        self.id = id
        self.context = context
        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=self.context.account_id, region=self.context.region),
        )
        Tags.of(scope=cast(IConstruct, self)).add(key="Env", value=f"orbit-{self.context.name}")
        if self.context.networking.vpc_id is None:
            raise ValueError("self.context.networking.vpc_id is None.")
        if self.context.networking.availability_zones is None:
            raise ValueError("self.context.networking.availability_zones is None.")
        # Checks if CodeArtifact exists outside of the scope of Orbit, else creates it.
        if not self.context.codeartifact_domain and not self.context.codeartifact_repository:
            DeployCodeArtifact(self, id="CodeArtifact-from-Env")

        self.i_vpc = ec2.Vpc.from_vpc_attributes(
            scope=self,
            id="vpc",
            vpc_id=self.context.networking.vpc_id,
            availability_zones=self.context.networking.availability_zones,
        )
        self.role_eks_cluster = self._create_role_cluster()
        self.role_eks_env_nodegroup = self._create_env_nodegroup_role()
        self.role_fargate_profile = self._create_role_fargate_profile()
        self.role_cluster_autoscaler = self._create_cluster_autoscaler_role()
        if self.context.user_pool_id:
            self.context.cognito_users_url = orbit_cognito.get_users_url(
                user_pool_id=self.context.user_pool_id, region=self.context.region
            )
            cognito_pool_arn: str = orbit_cognito.get_pool_arn(
                user_pool_id=self.context.user_pool_id, region=self.context.region, account=self.context.account_id
            )
            self.user_pool: cognito.UserPool = self._get_user_pool(user_pool_arn=cognito_pool_arn)
        else:
            raise Exception("Missing Cognito User Pool ID ('user_pool_id') ")
        self.user_pool_client = self._create_user_pool_client()
        self.identity_pool = self._create_identity_pool()
        self.token_validation_lambda = self._create_token_validation_lambda()
        self.eks_service_lambda = self._create_eks_service_lambda()
        self.cluster_pod_security_group = self._create_cluster_pod_security_group()
        self.context_parameter = self._create_manifest_parameter()
        self._create_post_authentication_lambda()

    def _create_role_cluster(self) -> iam.Role:
        name: str = f"orbit-{self.context.name}-{self.context.region}-eks-cluster-role"
        role = iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=cast(
                iam.IPrincipal,
                iam.CompositePrincipal(
                    iam.ServicePrincipal("eks.amazonaws.com"),
                    iam.ServicePrincipal("eks-fargate-pods.amazonaws.com"),
                ),
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
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["iam:AttachRolePolicy", "iam:PutRolePolicy", "s3:*"],
                            resources=[
                                "arn:aws:iam::*:role/aws-service-role/s3.data-source.lustre.fsx.amazonaws.com/",
                                f"{self.context.scratch_bucket_arn}",
                                f"{self.context.scratch_bucket_arn}/*",
                            ],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "iam:CreateServiceLinkedRole",
                                "s3:ListBucket",
                                "fsx:CreateFileSystem",
                                "fsx:DeleteFileSystem",
                                "fsx:DescribeFileSystems",
                                "fsx:TagResource",
                            ],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )

        return role

    def _create_role_fargate_profile(self) -> iam.Role:
        name: str = f"orbit-{self.context.name}-{self.context.region}-eks-fargate-profile-role"
        return iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=cast(
                iam.IPrincipal,
                iam.CompositePrincipal(
                    iam.ServicePrincipal("eks.amazonaws.com"),
                    iam.ServicePrincipal("eks-fargate-pods.amazonaws.com"),
                ),
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
        name: str = f"orbit-{self.context.name}-{self.context.region}-eks-nodegroup-role"
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
                iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonSSMManagedInstanceCore"),
            ],
        )
        return role

    def _create_cluster_autoscaler_role(self) -> iam.Role:
        name: str = f"orbit-{self.context.name}-{self.context.region}-cluster-autoscaler-role"
        return iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=cast(iam.IPrincipal, iam.ServicePrincipal("eks.amazonaws.com")),
            inline_policies={
                "Logging": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "autoscaling:DescribeAutoScalingGroups",
                                "autoscaling:DescribeAutoScalingInstances",
                                "autoscaling:DescribeLaunchConfigurations",
                                "autoscaling:DescribeTags",
                                "autoscaling:SetDesiredCapacity",
                                "autoscaling:TerminateInstanceInAutoScalingGroup",
                                "ec2:DescribeLaunchTemplateVersions",
                            ],
                            resources=["*"],
                        )
                    ]
                )
            },
        )

    def _get_user_pool(self, user_pool_arn: str) -> cognito.UserPool:
        return cast(
            cognito.UserPool,
            cognito.UserPool.from_user_pool_arn(scope=self, id="orbit-user-pool", user_pool_arn=user_pool_arn),
        )

    def _create_user_pool_client(self) -> cognito.UserPoolClient:
        return cognito.UserPoolClient(
            scope=self,
            id="user-pool-client",
            user_pool=cast(cognito.IUserPool, self.user_pool),
            auth_flows=cognito.AuthFlow(user_srp=True, admin_user_password=False, custom=False),
            generate_secret=True,
            prevent_user_existence_errors=True,
            user_pool_client_name="orbit",
        )

    def _create_identity_pool(self) -> cognito.CfnIdentityPool:
        provider_name = (
            self.user_pool.user_pool_provider_name
            if hasattr(self.user_pool, "user_pool_provider_name")
            else f"cognito-idp.{self.context.region}.amazonaws.com/{self.context.user_pool_id}"
        )

        pool = cognito.CfnIdentityPool(
            scope=self,
            id="identity-pool",
            identity_pool_name=self.id.replace("-", "_"),
            allow_unauthenticated_identities=False,
            allow_classic_flow=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    provider_name=provider_name,
                    client_id=self.user_pool_client.user_pool_client_id,
                )
            ],
        )
        name = f"{self.id}-{self.context.region}-cognito-authenticated-identity-role"
        authenticated_role = iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=cast(
                iam.IPrincipal,
                iam.FederatedPrincipal(
                    federated="cognito-identity.amazonaws.com",
                    conditions={
                        "StringEquals": {"cognito-identity.amazonaws.com:aud": pool.ref},
                        "ForAnyValue:StringLike": {"cognito-identity.amazonaws.com:amr": "authenticated"},
                    },
                    assume_role_action="sts:AssumeRoleWithWebIdentity",
                ),
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
                                f"arn:aws:ssm:{self.context.region}:{self.context.account_id}:"
                                f"parameter/orbit/{self.context.name}/teams/*"
                            ],
                        )
                    ]
                ),
            },
        )
        name = f"{self.id}-{self.context.region}-cognito-unauthenticated-identity-role"
        unauthenticated_role = iam.Role(
            scope=self,
            id=name,
            role_name=name,
            assumed_by=cast(
                iam.IPrincipal,
                iam.FederatedPrincipal(
                    federated="cognito-identity.amazonaws.com",
                    conditions={
                        "StringEquals": {"cognito-identity.amazonaws.com:aud": pool.ref},
                        "ForAnyValue:StringLike": {"cognito-identity.amazonaws.com:amr": "unauthenticated"},
                    },
                    assume_role_action="sts:AssumeRoleWithWebIdentity",
                ),
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
            function_name=f"orbit-{self.context.name}-token-validation",
            entry=_lambda_path("token_validation"),
            index="index.py",
            handler="handler",
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            timeout=Duration.seconds(5),
            environment={
                "COGNITO_USER_POOL_ID": self.user_pool.user_pool_id,
                "REGION": self.context.region,
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

    def _create_eks_service_lambda(self) -> aws_lambda.Function:

        return lambda_python.PythonFunction(
            scope=self,
            id="eks_service_lambda",
            function_name=f"orbit-{self.context.name}-eks-service-handler",
            entry=_lambda_path("eks_service_handler"),
            index="index.py",
            handler="handler",
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            timeout=Duration.seconds(5),
            environment={
                "REGION": self.context.region,
            },
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["eks:List*", "eks:Describe*"],
                    resources=[
                        f"arn:aws:eks:{self.context.region}:{self.context.account_id}:cluster/orbit-*",
                        f"arn:aws:eks:{self.context.region}:{self.context.account_id}:nodegroup/orbit-*/*/*",
                    ],
                )
            ],
        )

    def _create_post_authentication_lambda(self) -> None:
        k8s_layer_name = f"orbit-{self.context.name}-k8s-base-layer"

        sam_app = sam.CfnApplication(
            scope=self,
            id="awscli_kubectl_helm_lambda_layer_sam",
            location=sam.CfnApplication.ApplicationLocationProperty(
                application_id="arn:aws:serverlessrepo:us-east-1:903779448426:applications/lambda-layer-kubectl",
                semantic_version="2.0.0",
            ),
            parameters={"LayerName": k8s_layer_name},
        )

        role_name = self.context.toolkit.admin_role
        role_arn = f"arn:aws:iam::{self.context.account_id}:role/{role_name}"

        lambda_python.PythonFunction(
            scope=self,
            id="cognito_post_authentication_lambda",
            function_name=f"orbit-{self.context.name}-post-authentication",
            entry=_lambda_path("cognito_post_authentication"),
            index="index.py",
            handler="handler",
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            timeout=Duration.seconds(300),
            role=iam.Role.from_role_arn(scope=self, id="cognito-post-auth-role", role_arn=role_arn),
            environment={
                "REGION": self.context.region,
                "ORBIT_ENV": self.context.name,
                "ACCOUNT_ID": self.context.account_id,
            },
            memory_size=128,
        ).add_permission(
            id="cognito_post_auth_resource_policy",
            principal=cast(iam.IPrincipal, iam.ServicePrincipal("cognito-idp.amazonaws.com")),
            action="lambda:InvokeFunction",
            source_arn=(
                f"arn:aws:cognito-idp:{self.context.region}:{self.context.account_id}:"
                f"userpool/{self.user_pool.user_pool_id}"
            ),
        )

        lambda_python.PythonFunction(
            scope=self,
            id="cognito_post_authentication_k8s_lambda",
            entry=_lambda_path("cognito_post_authentication"),
            function_name=f"orbit-{self.context.name}-post-auth-k8s-manage",
            index="k8s_manage.py",
            handler="handler",
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            timeout=Duration.seconds(300),
            role=iam.Role.from_role_arn(scope=self, id="cognito-post-auth-k8s-role", role_arn=role_arn),
            environment={
                "REGION": self.context.region,
                "PATH": "/var/lang/bin:/usr/local/bin:/usr/bin/:/bin:/opt/bin:/opt/awscli:/opt/kubectl:/opt/helm",
                "ORBIT_ENV": self.context.name,
                "ACCOUNT_ID": self.context.account_id,
            },
            layers=[
                aws_lambda.LayerVersion.from_layer_version_arn(
                    scope=self,
                    id="K8sLambdaLayer",
                    layer_version_arn=(sam_app.get_att("Outputs.LayerVersionArn").to_string()),
                )
            ],
            memory_size=256,
        )

    def _create_manifest_parameter(self) -> ssm.StringParameter:
        parameter: ssm.StringParameter = ssm.StringParameter(
            scope=self,
            id="/orbit/EnvParams",
            string_value=json.dumps(
                {
                    "EksClusterRoleArn": self.role_eks_cluster.role_arn,
                    "EksFargateProfileRoleArn": self.role_fargate_profile.role_arn,
                    "EksEnvNodegroupRoleArn": self.role_eks_env_nodegroup.role_arn,
                    "EksClusterAutoscalerRoleArn": self.role_cluster_autoscaler.role_arn,
                    "UserPoolId": self.user_pool.user_pool_id,
                    "UserPoolClientId": self.user_pool_client.user_pool_client_id,
                    "IdentityPoolId": self.identity_pool.ref,
                    "ClusterPodSecurityGroupId": self.cluster_pod_security_group.security_group_id,
                }
            ),
            type=ssm.ParameterType.STRING,
            description="Orbit Workbench Remote Env.",
            parameter_name=self.context.env_ssm_parameter_name,
            simple_name=False,
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        )
        return parameter

    def _create_cluster_pod_security_group(self) -> ec2.SecurityGroup:
        name = f"orbit-{self.context.name}-cluster-pod-sg"
        sg = ec2.SecurityGroup(
            scope=self,
            id="cluster-pod-security-group",
            security_group_name=name,
            vpc=self.i_vpc,
        )
        Tags.of(scope=cast(IConstruct, sg)).add(key="Name", value=name)
        return sg


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 2:
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=sys.argv[1], type=Context)
    else:
        raise ValueError(f"Unexpected number of values in sys.argv ({len(sys.argv)}), {sys.argv}")

    outdir = os.path.join(".orbit.out", context.name, "cdk", context.env_stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    app = App(outdir=outdir)
    Env(
        scope=app,
        id=context.env_stack_name,
        context=context,
    )
    app.synth(force=True)


if __name__ == "__main__":
    main()
