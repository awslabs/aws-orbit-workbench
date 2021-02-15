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
from typing import TYPE_CHECKING, Any, Dict, List, cast

import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_kms as kms
import aws_cdk.aws_s3 as s3
import aws_cdk.core as core
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from aws_cdk.core import App, CfnOutput, Construct, Duration, Stack, Tags

from aws_orbit.models.context import load_context_from_ssm
from aws_orbit.remote_files.cdk.team_builders.cognito import CognitoBuilder
from aws_orbit.remote_files.cdk.team_builders.efs import EfsBuilder
from aws_orbit.remote_files.cdk.team_builders.s3 import S3Builder

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


class DemoStack(Stack):
    def __init__(self, scope: Construct, id: str, context: "Context", **kwargs: Any) -> None:
        self.env_name = context.name
        self.context = context
        super().__init__(scope, id, **kwargs)
        Tags.of(scope=cast(core.IConstruct, self)).add(key="Env", value=f"orbit-{self.env_name}")
        self.vpc: ec2.Vpc = self._create_vpc()

        self.public_subnets = (
            self.vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC)
            if self.vpc.public_subnets
            else self.vpc.select_subnets(subnet_name="")
        )
        self.private_subnets = (
            self.vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE)
            if self.vpc.private_subnets
            else self.vpc.select_subnets(subnet_name="")
        )
        self.isolated_subnets = (
            self.vpc.select_subnets(subnet_type=ec2.SubnetType.ISOLATED)
            if self.vpc.isolated_subnets
            else self.vpc.select_subnets(subnet_name="")
        )
        self.nodes_subnets = (
            self.private_subnets if context.networking.data.internet_accessible else self.isolated_subnets
        )

        self._create_vpc_endpoints()

        if context.toolkit.s3_bucket is None:
            raise ValueError("context.toolkit_s3_bucket is not defined")
        toolkit_s3_bucket_name: str = context.toolkit.s3_bucket
        acct: str = core.Aws.ACCOUNT_ID
        self.bucket_names: Dict[str, Any] = {
            "lake-bucket": f"orbit-{self.env_name}-demo-lake-{acct}-{context.toolkit.deploy_id}",
            "secured-lake-bucket": f"orbit-{self.env_name}-secured-demo-lake-{acct}-{context.toolkit.deploy_id}",
            "scratch-bucket": f"orbit-{self.env_name}-scratch-{acct}-{context.toolkit.deploy_id}",
            "toolkit-bucket": toolkit_s3_bucket_name,
        }
        self._build_kms_key_for_env()
        self.scratch_bucket: s3.Bucket = S3Builder.build_s3_bucket(
            scope=self,
            id="scratch_bucket",
            name=self.bucket_names["scratch-bucket"],
            scratch_retention_days=30,
            kms_key=self.env_kms_key,
        )
        self.lake_bucket: s3.Bucket = S3Builder.build_s3_bucket(
            scope=self,
            id="lake_bucket",
            name=self.bucket_names["lake-bucket"],
            scratch_retention_days=90,
            kms_key=self.env_kms_key,
        )
        self.secured_lake_bucket: s3.Bucket = S3Builder.build_s3_bucket(
            scope=self,
            id="secured_lake_bucket",
            name=self.bucket_names["secured-lake-bucket"],
            scratch_retention_days=90,
            kms_key=self.env_kms_key,
        )
        self.lake_bucket_full_access = self._create_fullaccess_managed_policies()
        self.lake_bucket_read_only_access = self._create_readonlyaccess_managed_policies()

        self.efs_fs = EfsBuilder.build_file_system(
            scope=self,
            name="orbit-fs",
            efs_life_cycle="AFTER_7_DAYS",
            vpc=self.vpc,
            efs_security_group=self._vpc_security_group,
            subnets=self.nodes_subnets.subnets,
            team_kms_key=self.env_kms_key,
        )

        self.user_pool: cognito.UserPool = self._create_user_pool()

        self.user_pool_lake_creator: cognito.CfnUserPoolGroup = CognitoBuilder.build_user_pool_group(
            scope=self, user_pool_id=self.user_pool.user_pool_id, team_name="lake-creator"
        )
        self.user_pool_lake_user: cognito.CfnUserPoolGroup = CognitoBuilder.build_user_pool_group(
            scope=self, user_pool_id=self.user_pool.user_pool_id, team_name="lake-user"
        )

        self._ssm_parameter = ssm.StringParameter(
            self,
            id="/orbit/DemoParams",
            string_value=json.dumps(
                {
                    "VpcId": self.vpc.vpc_id,
                    "PublicSubnets": self.public_subnets.subnet_ids,
                    "PrivateSubnets": self.private_subnets.subnet_ids,
                    "IsolatedSubnets": self.isolated_subnets.subnet_ids,
                    "NodesSubnets": self.nodes_subnets.subnet_ids,
                    "LoadBalancersSubnets": self.public_subnets.subnet_ids,
                    "LakeBucket": self.bucket_names["lake-bucket"],
                    "SecuredLakeBucket": self.bucket_names["secured-lake-bucket"],
                    "CreatorAaccessPolicy": self.lake_bucket_full_access.managed_policy_name,
                    "UserAccessPolicy": self.lake_bucket_read_only_access.managed_policy_name,
                    "KMSKey": self.env_kms_key.key_arn,
                    "SharedEfsFsId": self.efs_fs.file_system_id,
                    "ScratchBucketArn": self.scratch_bucket.bucket_arn,
                    "ScratchBucketName": self.scratch_bucket.bucket_name,
                    "UserPoolId": self.user_pool.user_pool_id,
                    "SharedEfsSgId": self._vpc_security_group.security_group_id,
                    "UserPoolProviderName": self.user_pool.user_pool_provider_name,
                }
            ),
            type=ssm.ParameterType.STRING,
            description="Orbit Workbench Demo resources.",
            parameter_name=self.context.demo_ssm_parameter_name,
            simple_name=False,
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        )

        CfnOutput(
            scope=self,
            id=f"{id}vpcid",
            export_name=f"orbit-{self.env_name}-vpc-id",
            value=self.vpc.vpc_id,
        )

        CfnOutput(
            scope=self,
            id=f"{id}publicsubnetsids",
            export_name=f"orbit-{self.env_name}-public-subnet-ids",
            value=",".join(self.public_subnets.subnet_ids),
        )
        CfnOutput(
            scope=self,
            id=f"{id}privatesubnetsids",
            export_name=f"orbit-{self.env_name}-private-subnet-ids",
            value=",".join(self.private_subnets.subnet_ids),
        )
        CfnOutput(
            scope=self,
            id=f"{id}isolatedsubnetsids",
            export_name=f"orbit-{self.env_name}-isolated-subnet-ids",
            value=",".join(self.isolated_subnets.subnet_ids),
        )
        CfnOutput(
            scope=self,
            id=f"{id}nodesubnetsids",
            export_name=f"orbit-{self.env_name}-nodes-subnet-ids",
            value=",".join(self.nodes_subnets.subnet_ids),
        )

        CfnOutput(
            scope=self,
            id=f"{id}lakebucketfullaccesspolicy",
            export_name="lake-bucket-full-access-policy",
            value=self.lake_bucket_full_access.managed_policy_name,
        )

        CfnOutput(
            scope=self,
            id=f"{id}lakebucketreadonlypolicy",
            export_name="lake-bucket-read-only-policy",
            value=self.lake_bucket_read_only_access.managed_policy_name,
        )

    def _build_kms_key_for_env(self) -> None:
        administrator_arns: List[str] = []  # A place to add other admins if needed for KMS
        admin_principals = iam.CompositePrincipal(
            *[iam.ArnPrincipal(arn) for arn in administrator_arns],
            iam.ArnPrincipal(f"arn:aws:iam::{self.context.account_id}:root"),
        )
        self.env_kms_key: kms.Key = kms.Key(
            self,
            id="kms-key",
            removal_policy=core.RemovalPolicy.RETAIN,
            enabled=True,
            enable_key_rotation=True,
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW, actions=["kms:*"], resources=["*"], principals=[admin_principals]
                    )
                ]
            ),
        )

    def _create_vpc(self) -> ec2.Vpc:
        vpc = ec2.Vpc(
            scope=self,
            id="vpc",
            default_instance_tenancy=ec2.DefaultInstanceTenancy.DEFAULT,
            cidr="10.0.0.0/16",
            enable_dns_hostnames=True,
            enable_dns_support=True,
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE, cidr_mask=21),
                ec2.SubnetConfiguration(name="Isolated", subnet_type=ec2.SubnetType.ISOLATED, cidr_mask=21),
            ],
            flow_logs={
                "all-traffic": ec2.FlowLogOptions(
                    destination=ec2.FlowLogDestination.to_cloud_watch_logs(), traffic_type=ec2.FlowLogTrafficType.ALL
                )
            },
        )
        return vpc

    def _create_user_pool(self) -> cognito.UserPool:
        pool = cognito.UserPool(
            scope=self,
            id="orbit-user-pool",
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
                email_subject="Invite to join Orbit Workbench!",
                email_body="Hello, you have been invited to join Orbit Workbench!<br/><br/>"
                "Username: {username}<br/>"
                "Temporary password: {####}<br/><br/>"
                "Regards",
            ),
            user_pool_name=f"orbit-{self.env_name}-user-pool",
        )
        return pool

    def _create_vpc_endpoints(self) -> None:
        vpc_gateway_endpoints = {
            "s3": ec2.GatewayVpcEndpointAwsService.S3,
            "dynamodb": ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        }
        vpc_interface_endpoints = {
            "cloudwatch_endpoint": ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH,
            "cloudwatch_logs_endpoint": ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            "cloudwatch_events": ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_EVENTS,
            "ecr_docker_endpoint": ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            "ecr_endpoint": ec2.InterfaceVpcEndpointAwsService.ECR,
            "ec2_endpoint": ec2.InterfaceVpcEndpointAwsService.EC2,
            "ecs": ec2.InterfaceVpcEndpointAwsService.ECS,
            "ecs_agent": ec2.InterfaceVpcEndpointAwsService.ECS_AGENT,
            "ecs_telemetry": ec2.InterfaceVpcEndpointAwsService.ECS_TELEMETRY,
            "git_endpoint": ec2.InterfaceVpcEndpointAwsService.CODECOMMIT_GIT,
            "ssm_endpoint": ec2.InterfaceVpcEndpointAwsService.SSM,
            "ssm_messages_endpoint": ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            "secrets_endpoint": ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            "kms_endpoint": ec2.InterfaceVpcEndpointAwsService.KMS,
            "sagemaker_endpoint": ec2.InterfaceVpcEndpointAwsService.SAGEMAKER_API,
            "sagemaker_runtime": ec2.InterfaceVpcEndpointAwsService.SAGEMAKER_RUNTIME,
            "notebook_endpoint": ec2.InterfaceVpcEndpointAwsService.SAGEMAKER_NOTEBOOK,
            "athena_endpoint": ec2.InterfaceVpcEndpointAwsService("athena"),
            "glue_endpoint": ec2.InterfaceVpcEndpointAwsService("glue"),
            "sqs": ec2.InterfaceVpcEndpointAwsService.SQS,
            "step_function_endpoint": ec2.InterfaceVpcEndpointAwsService("states"),
            "sns_endpoint": ec2.InterfaceVpcEndpointAwsService.SNS,
            "kinesis_firehose_endpoint": ec2.InterfaceVpcEndpointAwsService("kinesis-firehose"),
            "api_gateway": ec2.InterfaceVpcEndpointAwsService.APIGATEWAY,
            "sts_endpoint": ec2.InterfaceVpcEndpointAwsService.STS,
            "efs": ec2.InterfaceVpcEndpointAwsService.ELASTIC_FILESYSTEM,
            "elb": ec2.InterfaceVpcEndpointAwsService.ELASTIC_LOAD_BALANCING,
            "autoscaling": ec2.InterfaceVpcEndpointAwsService("autoscaling"),
        }

        for name, gateway_vpc_endpoint_service in vpc_gateway_endpoints.items():
            self.vpc.add_gateway_endpoint(
                id=name,
                service=gateway_vpc_endpoint_service,
                subnets=[
                    ec2.SubnetSelection(subnets=self.nodes_subnets.subnets),
                ],
            )

        for name, interface_service in vpc_interface_endpoints.items():
            self.vpc.add_interface_endpoint(
                id=name,
                service=interface_service,
                subnets=ec2.SubnetSelection(subnets=self.nodes_subnets.subnets),
                private_dns_enabled=True,
            )
        # Adding CodeArtifact VPC endpoints
        self.vpc.add_interface_endpoint(
            id="code_artifact_repo_endpoint",
            service=cast(
                ec2.IInterfaceVpcEndpointService, ec2.InterfaceVpcEndpointAwsService("codeartifact.repositories")
            ),
            subnets=ec2.SubnetSelection(subnets=self.nodes_subnets.subnets),
            private_dns_enabled=False,
        )
        self.vpc.add_interface_endpoint(
            id="code_artifact_api_endpoint",
            service=cast(ec2.IInterfaceVpcEndpointService, ec2.InterfaceVpcEndpointAwsService("codeartifact.api")),
            subnets=ec2.SubnetSelection(subnets=self.nodes_subnets.subnets),
            private_dns_enabled=False,
        )

        # Adding Lambda and Redshift endpoints with CDK low level APIs
        endpoint_url_template = "com.amazonaws.{}.{}"
        self._vpc_security_group = ec2.SecurityGroup(self, "vpc-sg", vpc=self.vpc, allow_all_outbound=False)
        # Adding ingress rule to VPC CIDR
        self._vpc_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block), connection=ec2.Port.all_tcp()
        )

        ec2.CfnVPCEndpoint(
            self,
            "redshift_endpoint",
            vpc_endpoint_type="Interface",
            service_name=endpoint_url_template.format(self.region, "redshift"),
            vpc_id=self.vpc.vpc_id,
            security_group_ids=[self._vpc_security_group.security_group_id],
            subnet_ids=self.nodes_subnets.subnet_ids,
            private_dns_enabled=True,
        )
        ec2.CfnVPCEndpoint(
            self,
            "lambda_endpoint",
            vpc_endpoint_type="Interface",
            service_name=endpoint_url_template.format(self.region, "lambda"),
            vpc_id=self.vpc.vpc_id,
            security_group_ids=[self._vpc_security_group.security_group_id],
            subnet_ids=self.nodes_subnets.subnet_ids,
            private_dns_enabled=True,
        )

    def _create_fullaccess_managed_policies(self) -> iam.ManagedPolicy:
        lake_bucket_full_access = iam.ManagedPolicy(
            self,
            "LakeBucketFullAccess",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:*",
                    ],
                    resources=[
                        self.lake_bucket.bucket_arn,
                        f"{self.lake_bucket.bucket_arn}*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["glue:*"],
                    resources=["*"],
                ),
            ],
            managed_policy_name=f"orbit-{self.env_name}-demo-lake-bucket-fullaccess",
        )
        return lake_bucket_full_access

    def _create_readonlyaccess_managed_policies(self) -> iam.ManagedPolicy:
        lake_bucket_read_only_access = iam.ManagedPolicy(
            self,
            "LakeBucketReadOnlyAccess",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:Get*", "s3:List*"],
                    resources=[
                        self.lake_bucket.bucket_arn,
                        f"{self.lake_bucket.bucket_arn}*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["glue:*"],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["kms:*"],
                    resources=[self.env_kms_key.key_arn],
                ),
            ],
            managed_policy_name=f"orbit-{self.env_name}-demo-lake-bucket-readonlyaccess",
        )
        return lake_bucket_read_only_access


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 2:
        context: "Context" = load_context_from_ssm(env_name=sys.argv[1])
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    outdir = os.path.join(".orbit.out", context.name, "cdk", context.demo_stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    app = App(outdir=outdir)
    DemoStack(scope=app, id=context.demo_stack_name, context=context)
    app.synth(force=True)


if __name__ == "__main__":
    main()
