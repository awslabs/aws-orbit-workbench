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
import aws_cdk.aws_efs as efs
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_ssm as ssm
from aws_cdk.core import App, Construct, Environment, Stack, Tags

from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.subnet import SubnetKind
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.remote_files.cdk.team_builders._lambda import LambdaBuilder
from datamaker_cli.remote_files.cdk.team_builders.ec2 import Ec2Builder
from datamaker_cli.remote_files.cdk.team_builders.ecs import EcsBuilder
from datamaker_cli.remote_files.cdk.team_builders.iam import IamBuilder
from datamaker_cli.remote_files.cdk.team_builders.s3 import S3Builder

_logger: logging.Logger = logging.getLogger(__name__)


class Team(Stack):
    def __init__(self, scope: Construct, id: str, manifest: Manifest, team_manifest: TeamManifest) -> None:
        self.scope = scope
        self.id = id
        self.manifest = manifest
        self.team_manifest = team_manifest
        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=self.manifest.account_id, region=self.manifest.region),
        )
        Tags.of(scope=self).add(key="Env", value=f"datamaker-{self.manifest.name}")
        Tags.of(scope=self).add(key="TeamSpace", value=self.team_manifest.name)
        self.i_vpc = ec2.Vpc.from_vpc_attributes(
            scope=self,
            id="vpc",
            vpc_id=self.manifest.vpc.vpc_id,
            availability_zones=self.manifest.vpc.availability_zones,
        )
        self.i_isolated_subnets = Ec2Builder.build_subnets_from_kind(
            scope=self, subnet_manifests=manifest.vpc.subnets, subnet_kind=SubnetKind.isolated
        )
        self.i_private_subnets = Ec2Builder.build_subnets_from_kind(
            scope=self, subnet_manifests=manifest.vpc.subnets, subnet_kind=SubnetKind.private
        )
        self.ecr_repo: ecr.Repository = self._create_repo()
        self.policy: str = str(self.team_manifest.policy)
        self.scratch_bucket: s3.Bucket = S3Builder.build_scratch_bucket(
            scope=self, manifest=manifest, team_manifest=team_manifest
        )
        self.role_eks_nodegroup = IamBuilder.build_team_role(
            scope=self,
            manifest=self.manifest,
            team_manifest=self.team_manifest,
            policy_name=self.policy,
            scratch_bucket=self.scratch_bucket,
        )
        self.sg_efs: ec2.SecurityGroup = Ec2Builder.build_efs_security_group(
            scope=self, manifest=manifest, team_manifest=team_manifest, vpc=self.i_vpc
        )
        self.efs: efs.FileSystem = self._create_efs()
        self.user_pool_group: cognito.CfnUserPoolGroup = self._create_user_pool_group()
        self.ecs_cluster = EcsBuilder.build_cluster(
            scope=self, manifest=manifest, team_manifest=team_manifest, vpc=self.i_vpc
        )
        self.ecs_execution_role = IamBuilder.build_ecs_role(scope=self)
        self.ecs_task_definition = EcsBuilder.build_task_definition(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            ecs_execution_role=self.ecs_execution_role,
            ecs_task_role=self.role_eks_nodegroup,
            file_system=self.efs,
        )
        self.ecs_container_runner = LambdaBuilder.build_ecs_container_runner(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            ecs_execution_role=self.ecs_execution_role,
            ecs_task_role=self.role_eks_nodegroup,
            ecs_cluster=self.ecs_cluster,
            ecs_task_definition=self.ecs_task_definition,
            efs_security_group=self.sg_efs,
            subnets=self.i_isolated_subnets if self.manifest.isolated_networking else self.i_private_subnets,
        )
        self.manifest_parameter = self._create_manifest_parameter()

    def _create_repo(self) -> ecr.Repository:
        return ecr.Repository(
            scope=self,
            id="repo",
            repository_name=f"datamaker-{self.manifest.name}-{self.team_manifest.name}",
        )

    def _create_efs(self) -> efs.FileSystem:
        name: str = f"datamaker-{self.manifest.name}-{self.team_manifest.name}-fs"
        subnets: List[ec2.ISubnet] = (
            self.i_isolated_subnets if self.manifest.isolated_networking else self.i_private_subnets
        )
        fs = efs.FileSystem(
            scope=self,
            id=name,
            file_system_name=name,
            vpc=self.i_vpc,
            encrypted=False,
            lifecycle_policy=None,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            throughput_mode=efs.ThroughputMode.BURSTING,
            security_group=cast(ec2.ISecurityGroup, self.sg_efs),
            vpc_subnets=ec2.SubnetSelection(subnets=subnets),
        )
        return fs

    def _create_user_pool_group(self) -> cognito.CfnUserPoolGroup:
        if self.manifest.user_pool_id is None:
            raise RuntimeError("Empty manifest.user_pool_id")
        return cognito.CfnUserPoolGroup(
            scope=self,
            id=f"{self.team_manifest.name}_group",
            user_pool_id=self.manifest.user_pool_id,
            group_name=self.team_manifest.name,
            description=f"{self.team_manifest.name} users group.",
        )

    def _create_manifest_parameter(self) -> ssm.StringParameter:
        self.team_manifest.efs_id = self.efs.file_system_id
        self.team_manifest.eks_nodegroup_role_arn = self.role_eks_nodegroup.role_arn
        self.team_manifest.scratch_bucket = self.scratch_bucket.bucket_name
        self.team_manifest.ecs_cluster_name = self.ecs_cluster.cluster_name
        self.team_manifest.ecs_task_definition_arn = self.ecs_task_definition.task_definition_arn
        self.team_manifest.ecs_container_runner_arn = self.ecs_container_runner.function_arn

        parameter: ssm.StringParameter = ssm.StringParameter(
            scope=self,
            id=self.team_manifest.ssm_parameter_name,
            string_value=self.team_manifest.asjson(),
            type=ssm.ParameterType.STRING,
            description="DataMaker Team Context.",
            parameter_name=self.team_manifest.ssm_parameter_name,
            simple_name=False,
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        )
        return parameter


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 3:
        filename: str = sys.argv[1]
        team_name: str = sys.argv[2]
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    manifest: Manifest = Manifest(filename=filename)
    manifest.fillup()

    for team in manifest.teams:
        if team.name == team_name:
            team_manifest: TeamManifest = team
            break
    else:
        raise ValueError(f"Team {team_name} not found in the manifest.")

    outdir = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, "cdk", team_manifest.stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    app = App(outdir=outdir)
    Team(scope=app, id=team_manifest.stack_name, manifest=manifest, team_manifest=team_manifest)
    app.synth(force=True)


if __name__ == "__main__":
    main()
