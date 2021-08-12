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
from typing import Any, Dict, List, cast

from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from aws_cdk import core
from aws_cdk.core import App, CfnOutput, Construct, Duration, Stack, Tags

from aws_orbit.models.context import ContextSerDe, FoundationContext
from aws_orbit.remote_files.cdk.team_builders.codeartifact import DeployCodeArtifact
from aws_orbit.remote_files.cdk.team_builders.efs import EfsBuilder
from aws_orbit.remote_files.cdk.team_builders.s3 import S3Builder

_logger: logging.Logger = logging.getLogger(__name__)


class FoundationStack(Stack):
    def __init__(
        self, scope: Construct, id: str, context: "FoundationContext", ssl_cert_arn: str, **kwargs: Any
    ) -> None:
        self.env_name = context.name
        self.context = context
        self.ssl_cert_arn = ssl_cert_arn
        super().__init__(scope, id, **kwargs)
        Tags.of(scope=cast(core.IConstruct, self)).add(key="Env", value=f"orbit-{self.env_name}")
        self.vpc: ec2.Vpc = self._create_vpc(context)

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
        if not context.networking.data.internet_accessible:
            self.isolated_subnets = (
                self.vpc.select_subnets(subnet_type=ec2.SubnetType.ISOLATED)
                if self.vpc.isolated_subnets
                else self.vpc.select_subnets(subnet_name="")
            )
            self.nodes_subnets = self.isolated_subnets
        else:
            self.nodes_subnets = self.private_subnets

        self._vpc_security_group = ec2.SecurityGroup(
            self, "vpc-sg", vpc=cast(ec2.IVpc, self.vpc), allow_all_outbound=False
        )
        # Adding ingress rule to VPC CIDR
        self._vpc_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block), connection=ec2.Port.all_tcp()
        )

        if not context.networking.data.internet_accessible:
            self._create_vpc_endpoints()

        if context.toolkit.s3_bucket is None:
            raise ValueError("context.toolkit_s3_bucket is not defined")
        toolkit_s3_bucket_name: str = context.toolkit.s3_bucket
        acct: str = core.Aws.ACCOUNT_ID
        self.bucket_names: Dict[str, Any] = {
            "scratch-bucket": f"orbit-f-{self.env_name}-scratch-{acct}-{context.toolkit.deploy_id}",
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

        self.efs_fs = EfsBuilder.build_file_system(
            scope=self,
            name="orbit-fs",
            efs_life_cycle="AFTER_7_DAYS",
            vpc=cast(ec2.IVpc, self.vpc),
            efs_security_group=cast(ec2.ISecurityGroup, self._vpc_security_group),
            subnets=self.nodes_subnets.subnets,
            team_kms_key=self.env_kms_key,
        )

        self.user_pool: cognito.UserPool = self._create_user_pool()

        # Checks if CodeArtifact exists outside of the scope of Orbit, else creates it.
        if self.context.codeartifact_domain and self.context.codeartifact_repository:
            self.domain_name = self.context.codeartifact_domain
            self.repository_name = self.context.codeartifact_repository
        else:
            self.codeartifact = DeployCodeArtifact(self, id="CodeArtifact-from-Fndn")
            self.domain_name = self.codeartifact.artifact_domain.domain_name
            self.repository_name = self.codeartifact.pypi_repo.repository_name

        self._ssm_parameter = ssm.StringParameter(
            self,
            id="/orbit/DemoParams",
            string_value=json.dumps(
                {
                    "VpcId": self.vpc.vpc_id,
                    "PublicSubnets": self.public_subnets.subnet_ids,
                    "PrivateSubnets": self.private_subnets.subnet_ids,
                    "IsolatedSubnets": self.isolated_subnets.subnet_ids
                    if not context.networking.data.internet_accessible
                    else [],
                    "NodesSubnets": self.nodes_subnets.subnet_ids,
                    "LoadBalancersSubnets": self.public_subnets.subnet_ids,
                    "KMSKey": self.env_kms_key.key_arn,
                    "SharedEfsFsId": self.efs_fs.file_system_id,
                    "ScratchBucketArn": self.scratch_bucket.bucket_arn,
                    "ScratchBucketName": self.scratch_bucket.bucket_name,
                    "UserPoolId": self.user_pool.user_pool_id,
                    "SharedEfsSgId": self._vpc_security_group.security_group_id,
                    "UserPoolProviderName": self.user_pool.user_pool_provider_name,
                    "SslCertArn": self.ssl_cert_arn,
                    "CodeartifactDomain": self.domain_name,
                    "CodeartifactRepository": self.repository_name,
                    "IsCodeartifactExternal": True
                    if self.context.codeartifact_domain and self.context.codeartifact_repository
                    else False,
                }
            ),
            type=ssm.ParameterType.STRING,
            description="Orbit Workbench Demo resources.",
            parameter_name=context.resources_ssm_parameter_name,
            simple_name=False,
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        )

        CfnOutput(
            scope=self,
            id=f"{id}vpcid",
            export_name=f"orbit-f-{self.env_name}-vpc-id",
            value=self.vpc.vpc_id,
        )

        CfnOutput(
            scope=self,
            id=f"{id}publicsubnetsids",
            export_name=f"orbit-f-{self.env_name}-public-subnet-ids",
            value=",".join(self.public_subnets.subnet_ids),
        )
        CfnOutput(
            scope=self,
            id=f"{id}privatesubnetsids",
            export_name=f"orbit-f-{self.env_name}-private-subnet-ids",
            value=",".join(self.private_subnets.subnet_ids),
        )
        if not context.networking.data.internet_accessible:
            CfnOutput(
                scope=self,
                id=f"{id}isolatedsubnetsids",
                export_name=f"orbit-f-{self.env_name}-isolated-subnet-ids",
                value=",".join(self.isolated_subnets.subnet_ids),
            )
        CfnOutput(
            scope=self,
            id=f"{id}nodesubnetsids",
            export_name=f"orbit-f-{self.env_name}-nodes-subnet-ids",
            value=",".join(self.nodes_subnets.subnet_ids),
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
                        effect=iam.Effect.ALLOW,
                        actions=["kms:*"],
                        resources=["*"],
                        principals=[cast(iam.IPrincipal, admin_principals)],
                    )
                ]
            ),
        )

    def _create_vpc(self, context: "FoundationContext") -> ec2.Vpc:
        if context.networking.data.internet_accessible:
            subnet_configuration = [
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE, cidr_mask=21),
            ]
        else:
            subnet_configuration = [
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE, cidr_mask=21),
                ec2.SubnetConfiguration(name="Isolated", subnet_type=ec2.SubnetType.ISOLATED, cidr_mask=21),
            ]

        vpc = ec2.Vpc(
            scope=self,
            id="vpc",
            default_instance_tenancy=ec2.DefaultInstanceTenancy.DEFAULT,
            cidr="10.0.0.0/16",
            enable_dns_hostnames=True,
            enable_dns_support=True,
            max_azs=context.networking.max_availability_zones
            if context.networking.max_availability_zones is not None
            else 2,
            nat_gateways=1,
            subnet_configuration=subnet_configuration,
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
        pool.apply_removal_policy(policy=core.RemovalPolicy.DESTROY)
        pool.add_domain(
            id="orbit-user-pool-domain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"orbit-{self.context.account_id}-{self.env_name}"
            ),
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
            "cloudformation_endpoint": ec2.InterfaceVpcEndpointAwsService("cloudformation"),
            "codebuild_endpoint": ec2.InterfaceVpcEndpointAwsService("codebuild"),
            "emr-containers": ec2.InterfaceVpcEndpointAwsService("emr-containers"),
            "databrew": ec2.InterfaceVpcEndpointAwsService("databrew"),
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
                security_groups=[cast(ec2.ISecurityGroup, self._vpc_security_group)],
            )
        # Adding CodeArtifact VPC endpoints
        self.vpc.add_interface_endpoint(
            id="code_artifact_repo_endpoint",
            service=cast(
                ec2.IInterfaceVpcEndpointService, ec2.InterfaceVpcEndpointAwsService("codeartifact.repositories")
            ),
            subnets=ec2.SubnetSelection(subnets=self.nodes_subnets.subnets),
            private_dns_enabled=False,
            security_groups=[cast(ec2.ISecurityGroup, self._vpc_security_group)],
        )
        self.vpc.add_interface_endpoint(
            id="code_artifact_api_endpoint",
            service=cast(ec2.IInterfaceVpcEndpointService, ec2.InterfaceVpcEndpointAwsService("codeartifact.api")),
            subnets=ec2.SubnetSelection(subnets=self.nodes_subnets.subnets),
            private_dns_enabled=False,
            security_groups=[cast(ec2.ISecurityGroup, self._vpc_security_group)],
        )

        # Adding Lambda and Redshift endpoints with CDK low level APIs
        endpoint_url_template = "com.amazonaws.{}.{}"
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


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    context: "FoundationContext" = ContextSerDe.load_context_from_ssm(env_name=sys.argv[1], type=FoundationContext)
    ssl_cert_arn: str
    if len(sys.argv) == 3:
        ssl_cert_arn = sys.argv[2]
    elif len(sys.argv) == 2:
        ssl_cert_arn = ""
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    outdir = os.path.join(".orbit.out", context.name, "cdk", cast(str, context.stack_name))
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    app = App(
        outdir=outdir,
    )
    FoundationStack(
        scope=app,
        id=cast(str, context.stack_name),
        context=context,
        ssl_cert_arn=ssl_cert_arn,
        env=core.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"], region=os.environ["CDK_DEFAULT_REGION"]),
    )
    app.synth(force=True)


if __name__ == "__main__":
    main()
