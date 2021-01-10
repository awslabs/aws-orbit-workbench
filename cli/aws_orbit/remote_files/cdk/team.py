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
from typing import List

import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_efs as efs
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_ssm as ssm
from aws_cdk.core import App, Construct, Environment, Stack, Tags
from aws_orbit import changeset
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.subnet import SubnetKind
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.remote_files.cdk.team_builders._lambda import LambdaBuilder
from aws_orbit.remote_files.cdk.team_builders.cognito import CognitoBuilder
from aws_orbit.remote_files.cdk.team_builders.ec2 import Ec2Builder
from aws_orbit.remote_files.cdk.team_builders.ecs import EcsBuilder
from aws_orbit.remote_files.cdk.team_builders.efs import EfsBuilder
from aws_orbit.remote_files.cdk.team_builders.iam import IamBuilder
from aws_orbit.remote_files.cdk.team_builders.s3 import S3Builder
from aws_orbit.remote_files.cdk.team_builders.stepfunctions import StateMachineBuilder

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
        Tags.of(scope=self).add(key="Env", value=f"orbit-{self.manifest.name}")
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

        self.ecr_repo: ecr.Repository = ecr.Repository(
            scope=self,
            id="repo",
            repository_name=f"orbit-{self.manifest.name}-{self.team_manifest.name}",
        )

        self.policies: List[str] = self.team_manifest.policies

        self.scratch_bucket: s3.Bucket = S3Builder.build_scratch_bucket(
            scope=self, manifest=manifest, team_manifest=team_manifest
        )

        self.role_eks_nodegroup = IamBuilder.build_team_role(
            scope=self,
            manifest=self.manifest,
            team_manifest=self.team_manifest,
            policy_names=self.policies,
            scratch_bucket=self.scratch_bucket,
        )

        self.sg_efs: ec2.SecurityGroup = Ec2Builder.build_efs_security_group(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            vpc=self.i_vpc,
            subnet_kind=SubnetKind.private if manifest.internet_accessible else SubnetKind.isolated,
        )
        self.efs: efs.FileSystem = EfsBuilder.build_file_system(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            vpc=self.i_vpc,
            efs_security_group=self.sg_efs,
            subnets=self.i_private_subnets if self.manifest.internet_accessible else self.i_isolated_subnets,
        )

        self.user_pool_group: cognito.CfnUserPoolGroup = CognitoBuilder.build_user_pool_group(
            scope=self, manifest=manifest, team_manifest=team_manifest
        )

        self.ecs_cluster = EcsBuilder.build_cluster(
            scope=self, manifest=manifest, team_manifest=team_manifest, vpc=self.i_vpc
        )
        self.ecr_image = EcsBuilder.build_ecr_image(scope=self, manifest=manifest, team_manifest=team_manifest)
        self.ecs_execution_role = IamBuilder.build_ecs_role(scope=self)
        self.ecs_task_definition = EcsBuilder.build_task_definition(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            ecs_execution_role=self.ecs_execution_role,
            ecs_task_role=self.role_eks_nodegroup,
            file_system=self.efs,
            image=self.ecr_image,
        )
        self.container_runner_role = IamBuilder.build_container_runner_role(
            scope=self, manifest=manifest, team_manifest=team_manifest
        )
        self.ecs_fargate_runner = StateMachineBuilder.build_ecs_run_container_state_machine(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            cluster=self.ecs_cluster,
            task_definition=self.ecs_task_definition,
            efs_security_group=self.sg_efs,
            subnets=self.i_private_subnets if self.manifest.internet_accessible else self.i_isolated_subnets,
            role=self.container_runner_role,
            scratch_bucket=self.scratch_bucket,
        )
        self.eks_k8s_api = StateMachineBuilder.build_eks_k8s_api_state_machine(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
        )
        self.eks_fargate_runner = StateMachineBuilder.build_eks_run_container_state_machine(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            image=self.ecr_image,
            role=self.container_runner_role,
            node_type="fargate",
            k8s_api_state_machine=self.eks_k8s_api,
        )
        self.eks_ec2_runner = StateMachineBuilder.build_eks_run_container_state_machine(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            image=self.ecr_image,
            role=self.container_runner_role,
            node_type="ec2",
            k8s_api_state_machine=self.eks_k8s_api,
        )

        self.container_runner = LambdaBuilder.build_container_runner(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            ecs_fargate_runner=self.ecs_fargate_runner,
            eks_fargate_runner=self.eks_fargate_runner,
            eks_ec2_runner=self.eks_ec2_runner,
        )

        self.team_manifest.efs_id = self.efs.file_system_id
        self.team_manifest.eks_nodegroup_role_arn = self.role_eks_nodegroup.role_arn
        self.team_manifest.scratch_bucket = self.scratch_bucket.bucket_name
        self.team_manifest.ecs_cluster_name = self.ecs_cluster.cluster_name
        self.team_manifest.container_runner_arn = self.container_runner.function_arn
        self.team_manifest.eks_k8s_api_arn = self.eks_k8s_api.state_machine_arn

        self.manifest_parameter: ssm.StringParameter = ssm.StringParameter(
            scope=self,
            id=self.team_manifest.ssm_parameter_name,
            string_value=self.team_manifest.asjson(),
            type=ssm.ParameterType.STRING,
            description="Orbit Workbench Team Context.",
            parameter_name=self.team_manifest.ssm_parameter_name,
            simple_name=False,
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        )


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 3:
        filename: str = sys.argv[1]
        team_name: str = sys.argv[2]
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    manifest: Manifest = Manifest(filename=filename)
    manifest.fillup()

    changes: changeset.Changeset = changeset.read_changeset_file(
        manifest=manifest, filename=os.path.join(manifest.filename_dir, "changeset.json")
    )
    if changes.teams_changeset and team_name in changes.teams_changeset.removed_teams_names:
        for team in changes.teams_changeset.old_teams:
            if team.name == team_name:
                team_manifest: TeamManifest = team
                break
        else:
            raise ValueError(f"Team {team_name} not found in the teams_changeset.old_teams list.")
    else:
        for team in manifest.teams:
            if team.name == team_name:
                team_manifest = team
                break
        else:
            raise ValueError(f"Team {team_name} not found in the manifest.")

    outdir = os.path.join(manifest.filename_dir, ".orbit.out", manifest.name, "cdk", team_manifest.stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    app = App(outdir=outdir)
    Team(scope=app, id=team_manifest.stack_name, manifest=manifest, team_manifest=team_manifest)
    app.synth(force=True)


if __name__ == "__main__":
    main()
