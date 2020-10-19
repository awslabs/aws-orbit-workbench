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
            export_name=f"datamaker-{self.env_name}-public-subnets-ids",
            value=",".join(self.public_subnets_ids),
        )
        CfnOutput(
            scope=self,
            id=f"{id}privatesubnetsids",
            export_name=f"datamaker-{self.env_name}-private-subnets-ids",
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
        return vpc


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
