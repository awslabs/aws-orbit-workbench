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
from typing import Any, Tuple

import aws_cdk.core as core
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from aws_cdk.core import App, CfnOutput, Construct, Stack, Tags

from datamaker_cli.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


class DemoStack(Stack):
    def __init__(self, scope: Construct, id: str, manifest: Manifest, **kwargs: Any) -> None:
        self.env_name = manifest.name
        self.manifest = manifest
        super().__init__(scope, id, **kwargs)
        Tags.of(scope=self).add(key="Env", value=f"datamaker-{self.env_name}")
        self.vpc: ec2.Vpc = self._create_vpc()
        self.public_subnets_ids: Tuple[str, ...] = tuple(x.subnet_id for x in self.vpc.public_subnets)
        self.private_subnets_ids: Tuple[str, ...] = tuple(x.subnet_id for x in self.vpc.private_subnets)
        self.isolated_subnets_ids: Tuple[str, ...] = tuple(x.subnet_id for x in self.vpc.isolated_subnets)
        self._create_vpc_endpoints()
        # self.lake_bucket = self._create_lake_bucket()
        self.lake_bucket_name = (
            f"datamaker-{self.env_name}-demo-lake-{self.manifest.account_id}-{self.manifest.deploy_id}"
        )
        self.lake_bucket_full_access = self._create_fullaccess_managed_policies(bucket_name=self.lake_bucket_name)
        self.lake_bucket_read_only_access = self._create_readonlyaccess_managed_policies(
            bucket_name=self.lake_bucket_name
        )

        self._ssm_parameter = ssm.StringParameter(
            self,
            id="/datamaker/DemoParams",
            string_value=json.dumps(
                {
                    "vpc_id": self.vpc.vpc_id,
                    "public_subnet": self.public_subnets_ids,
                    "private_subnet": self.private_subnets_ids,
                    "lake_bucket": self.lake_bucket_name,
                    "creator_access_policy": self.lake_bucket_full_access.managed_policy_name,
                    "user_access_policy": self.lake_bucket_read_only_access.managed_policy_name,
                }
            ),
            type=ssm.ParameterType.STRING,
            description="DataMaker Demo resources.",
            parameter_name=f"/datamaker/{self.env_name}/demo",
            simple_name=False,
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        )

        CfnOutput(
            scope=self,
            id=f"{id}publicsubnetsids",
            export_name=f"datamaker-{self.env_name}-public-subnets-ids",
            value=",".join(self.public_subnets_ids),
        )
        CfnOutput(
            scope=self,
            id=f"{id}privatesubnetsids",
            export_name=f"datamaker-{self.env_name}-private-subnets-ids",
            value=",".join(self.private_subnets_ids),
        )
        CfnOutput(
            scope=self,
            id=f"{id}isolatedsubnetsids",
            export_name=f"datamaker-{self.env_name}-isolated-subnets-ids",
            value=",".join(self.isolated_subnets_ids),
        )

        CfnOutput(
            scope=self,
            id=f"{id}lakebucketname",
            export_name="lake-bucket-name",
            value=self.lake_bucket_name,
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

        for name, gateway_vpc_endpoint_service in vpc_gateway_endpoints.items():
            self.vpc.add_gateway_endpoint(
                id=name,
                service=gateway_vpc_endpoint_service,
                subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.ISOLATED)],
            )

        for name, interface_service in vpc_interface_endpoints.items():
            self.vpc.add_interface_endpoint(
                id=name,
                service=interface_service,
                subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.ISOLATED),
                private_dns_enabled=True,
            )
        # Adding CodeArtifact VPC endpoints
        self.vpc.add_interface_endpoint(
            id="code_artifact_repo_endpoint",
            service=ec2.InterfaceVpcEndpointAwsService("codeartifact.repositories"),
            private_dns_enabled=False,
        )
        self.vpc.add_interface_endpoint(
            id="code_artifact_api_endpoint",
            service=ec2.InterfaceVpcEndpointAwsService("codeartifact.api"),
            private_dns_enabled=False,
        )

        # Adding Lambda and Redshift endpoints with CDK low level APIs
        endpoint_url_template = "com.amazonaws.{}.{}"
        vpc_security_group = ec2.SecurityGroup(self, "vpc-sg", vpc=self.vpc, allow_all_outbound=False)
        # Adding ingress rule to VPC CIDR
        vpc_security_group.add_ingress_rule(peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block), connection=ec2.Port.all_tcp())
        isolated_subnet_ids = [t.subnet_id for t in self.vpc.isolated_subnets]

        ec2.CfnVPCEndpoint(
            self,
            "redshift_endpoint",
            vpc_endpoint_type="Interface",
            service_name=endpoint_url_template.format(self.region, "redshift"),
            vpc_id=self.vpc.vpc_id,
            security_group_ids=[vpc_security_group.security_group_id],
            subnet_ids=isolated_subnet_ids,
            private_dns_enabled=True,
        )
        ec2.CfnVPCEndpoint(
            self,
            "lambda_endpoint",
            vpc_endpoint_type="Interface",
            service_name=endpoint_url_template.format(self.region, "lambda"),
            vpc_id=self.vpc.vpc_id,
            security_group_ids=[vpc_security_group.security_group_id],
            subnet_ids=isolated_subnet_ids,
            private_dns_enabled=True,
        )

    # def _create_lake_bucket(self) -> s3.Bucket:
    #     lake_bucket = s3.Bucket(
    #         scope=self,
    #         id="lake_bucket",
    #         bucket_name=f"datamaker-{self.env_name}-demo-lake-{self.manifest.account_id}-{self.manifest.deploy_id}",
    #         block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    #         encryption=s3.BucketEncryption.S3_MANAGED,
    #     )
    #     return lake_bucket

    def _create_fullaccess_managed_policies(self, bucket_name: str) -> iam.ManagedPolicy:
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
                        f"arn:{core.Aws.PARTITION}:s3:::{bucket_name}",
                        f"arn:{core.Aws.PARTITION}:s3:::{bucket_name}/*",
                    ],
                )
            ],
            managed_policy_name=f"datamaker-{self.env_name}-lake-bucket-fullaccess",
        )
        return lake_bucket_full_access

    def _create_readonlyaccess_managed_policies(self, bucket_name: str) -> iam.ManagedPolicy:
        lake_bucket_read_only_access = iam.ManagedPolicy(
            self,
            "LakeBucketReadOnlyAccess",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:Get*", "s3:List*"],
                    resources=[
                        f"arn:{core.Aws.PARTITION}:s3:::{bucket_name}",
                        f"arn:{core.Aws.PARTITION}:s3:::{bucket_name}/*"
                        # bucket.arn_for_objects("*"),
                        # bucket.bucket_arn
                    ],
                ),
            ],
            managed_policy_name=f"datamaker-{self.env_name}-lake-bucket-readonlyaccess",
        )
        return lake_bucket_read_only_access


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 2:
        filename: str = sys.argv[1]
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    manifest: Manifest = Manifest(filename=filename)
    manifest.fillup()

    outdir = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, "cdk", manifest.demo_stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    app = App(outdir=outdir)
    DemoStack(scope=app, id=manifest.demo_stack_name, manifest=manifest)
    app.synth(force=True)


if __name__ == "__main__":
    main()
