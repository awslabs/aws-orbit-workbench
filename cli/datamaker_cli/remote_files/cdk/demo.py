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

import os
import shutil
from typing import Any, Tuple

import aws_cdk.aws_ec2 as ec2
from aws_cdk.core import App, CfnOutput, Construct, Stack, Tags

from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_route53 as r53,
    aws_route53_targets as targets,
)

from datamaker_cli.utils import path_from_filename


class VpcStack(Stack):
    def __init__(self, scope: Construct, id: str, env_name: str, **kwargs: Any) -> None:
        self.env_name = env_name
        super().__init__(scope, id, **kwargs)
        Tags.of(scope=self).add(key="Env", value=f"datamaker-{env_name}")
        self.vpc: ec2.Vpc = self._create_vpc()
        self.public_subnets_ids: Tuple[str, ...] = tuple(x.subnet_id for x in self.vpc.public_subnets)
        self.private_subnets_ids: Tuple[str, ...] = tuple(x.subnet_id for x in self.vpc.private_subnets)
        CfnOutput(
            scope=self,
            id=f"{id}publicsubnetsids",
            export_name=f"{id}-public-subnets-ids",
            value=",".join(self.public_subnets_ids),
        )
        CfnOutput(
            scope=self,
            id=f"{id}privatesubnetsids",
            export_name=f"{id}-private-subnets-ids",
            value=",".join(self.private_subnets_ids),
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
            ],
        )
        Tags.of(scope=vpc).add(key="Env", value=f"datamaker-{self.env_name}")
        return vpc


# WIP
# Adding VPC with isolated subnets and VPC endpoints
class NewVpcStack(Stack):
    def __init__(self, scope: Construct, id: str, env_name: str, **kwargs: Any) -> None:
        self.env_name = env_name
        super().__init__(scope, id, **kwargs)
        Tags.of(scope=self).add(key="Env", value=f"datamaker-{env_name}")
        self.vpc: ec2.Vpc = self._create_vpc()

        self.isolated_subnets_ids: Tuple[str, ...] = tuple(x.subnet_id for x in self.vpc.isolated_subnets)

        CfnOutput(
            scope=self,
            id=f"{id}isolatedsubnetsids",
            export_name=f"{id}-isolated-subnets-ids",
            value=",".join(self.isolated_subnets_ids),
        )


    def _create_vpc(self) -> ec2.Vpc:
        demo_vpc = ec2.Vpc(
            scope=self,
            id="vpc",
            default_instance_tenancy=ec2.DefaultInstanceTenancy.DEFAULT,
            cidr="10.191.0.0/16",
            enable_dns_hostnames=True,
            enable_dns_support=True,
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Isolated", subnet_type=ec2.SubnetType.ISOLATED)
            ],
            flow_logs=ec2.FlowLogOptions(
                destination=ec2.FlowLogDestination.to_cloud_watch_logs(),
                traffic_type=ec2.FlowLogTrafficType.ALL
            ),
            vpc_gateway_endpoints={
                "s3": ec2.GatewayVpcEndpointAwsService.S3,
                "dynamodb": ec2.GatewayVpcEndpointAwsService.DYNAMODB
            },
            vpc_interface_endpoints={
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
                "notebook_endpoint": ec2.InterfaceVpcEndpointAwsService.SAGEMAKER_NOTEBOOK,
                "athena_endpoint": ec2.InterfaceVpcEndpointAwsService('athena'),
                "glue_endpoint": ec2.InterfaceVpcEndpointAwsService('glue'),
                "sqs": ec2.InterfaceVpcEndpointAwsService.SQS,
                "step_function_endpoint": ec2.InterfaceVpcEndpointAwsService('states'),
                "sns_endpoint": ec2.InterfaceVpcEndpointAwsService.SNS,
                "kinesis_firehose_endpoint": ec2.InterfaceVpcEndpointAwsService('kinesis-firehose'),
                "api_gateway": ec2.InterfaceVpcEndpointAwsService.APIGATEWAY,
                "sts_endpoint": ec2.InterfaceVpcEndpointAwsService.STS
            }
        )

        #Adding CA endpoints
        CodeArtifactEndpoints(self, 'CodeArtifact', demo_vpc.vpc)

        #TODO - Add ServerAccessLogBucket

        Tags.of(scope=demo_vpc).add(key="Env", value=f"datamaker-{self.env_name}")
        return demo_vpc

class CodeArtifactEndpoints(core.Construct):
    def __init__(self, scope: core.Construct, id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc.add_interface_endpoint(
          'code_artifact_api_endpoint',
          service=ec2.InterfaceVpcEndpointAwsService('codeartifact.api')
        )

        code_artifact_repo_endpoint = vpc.add_interface_endpoint(
            'code_artifact_endpoint',
            service=ec2.InterfaceVpcEndpointAwsService('codeartifact.repositories'),
            private_dns_enabled=False
        )

        zone = r53.HostedZone(
            self,
            'CodeArtifactHostedZone',
            vpcs=[vpc],
            zone_name=f'd.codeartifact.{core.Aws.REGION}.amazonaws.com')

        r53.ARecord(
            self,
            'CodeArtifactRepoRecord',
            zone=zone,
            target=r53.RecordTarget.from_alias(targets.InterfaceVpcEndpointTarget(code_artifact_repo_endpoint)),
            record_name='*')

def synth(stack_name: str, filename: str, env_name: str) -> str:
    filename_dir = path_from_filename(filename=filename)
    outdir = os.path.join(filename_dir, ".datamaker.out", env_name, "cdk", stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)
    output_filename = os.path.join(outdir, f"{stack_name}.template.json")

    app = App(outdir=outdir)
    VpcStack(scope=app, id=stack_name, env_name=env_name)
    app.synth(force=True)
    return output_filename
