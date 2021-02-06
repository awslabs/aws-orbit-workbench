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

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_efs as efs
import aws_cdk.aws_iam as iam
import aws_cdk.aws_kms as kms
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_ssm as ssm
import aws_cdk.core as core
from aws_cdk.core import App, Construct, Environment, IConstruct, Stack, Tags

from aws_orbit import changeset
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.subnet import SubnetKind
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.remote_files.cdk.team_builders._lambda import LambdaBuilder
from aws_orbit.remote_files.cdk.team_builders.ec2 import Ec2Builder
from aws_orbit.remote_files.cdk.team_builders.ecs import EcsBuilder
from aws_orbit.remote_files.cdk.team_builders.efs import EfsBuilder
from aws_orbit.remote_files.cdk.team_builders.iam import IamBuilder
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
        Tags.of(scope=cast(IConstruct, self)).add(key="Env", value=f"orbit-{self.manifest.name}")
        Tags.of(scope=cast(IConstruct, self)).add(key="TeamSpace", value=self.team_manifest.name)

        self.i_vpc = ec2.Vpc.from_vpc_attributes(
            scope=self,
            id="vpc",
            vpc_id=cast(str, self.manifest.vpc.vpc_id),
            availability_zones=cast(List[str], self.manifest.vpc.availability_zones),
        )
        self.i_isolated_subnets = Ec2Builder.build_subnets_from_kind(
            scope=self, subnet_manifests=manifest.vpc.subnets, subnet_kind=SubnetKind.isolated
        )
        self.i_private_subnets = Ec2Builder.build_subnets_from_kind(
            scope=self, subnet_manifests=manifest.vpc.subnets, subnet_kind=SubnetKind.private
        )
        administrator_arns: List[str] = []  # A place to add other admins if needed for KMS
        admin_principals = iam.CompositePrincipal(
            *[iam.ArnPrincipal(arn) for arn in administrator_arns],
            iam.ArnPrincipal(f"arn:aws:iam::{self.manifest.account_id}:root"),
        )
        self.team_kms_key: kms.Key = kms.Key(
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
        self.team_security_group: ec2.SecurityGroup = Ec2Builder.build_team_security_group(
            scope=self, manifest=manifest, team_manifest=team_manifest, vpc=self.i_vpc
        )
        self.ecr_repo: ecr.Repository = ecr.Repository(
            scope=self,
            id="repo",
            repository_name=f"orbit-{self.manifest.name}-{self.team_manifest.name}",
        )

        self.ecr_repo_spark: ecr.Repository = ecr.Repository(
            scope=self,
            id="repo-spark",
            repository_name=f"orbit-{self.manifest.name}-{self.team_manifest.name}-spark",
        )

        self.policies: List[str] = self.team_manifest.policies
        if self.manifest.scratch_bucket_arn:
            self.scratch_bucket: s3.Bucket = cast(
                s3.Bucket,
                s3.Bucket.from_bucket_attributes(
                    scope=self,
                    id="scratch_bucket",
                    bucket_arn=self.manifest.scratch_bucket_arn,
                    bucket_name=self.manifest.scratch_bucket_arn.split(":::")[1],
                ),
            )
        else:
            raise Exception("Scratch bucket was not provided in Manifest ('scratch-bucket-arn')")

        self.role_eks_nodegroup = IamBuilder.build_team_role(
            scope=self,
            manifest=self.manifest,
            team_manifest=self.team_manifest,
            policy_names=self.policies,
            scratch_bucket=self.scratch_bucket,
            team_kms_key=self.team_kms_key,
        )
        shared_fs_name: str = f"orbit-{manifest.name}-{team_manifest.name}-shared-fs"
        if not manifest.shared_efs_fs_id:
            raise Exception("Shared EFS File system ID was not provided in Manifest ('shared-efs-fs-id')")

        if not manifest.shared_efs_sg_id:
            raise Exception(
                "Shared EFS File system security group ID was not provided in Manifest ('shared-efs-sg-id')"
            )

        self.shared_fs: efs.FileSystem = cast(
            efs.FileSystem,
            efs.FileSystem.from_file_system_attributes(
                scope=self,
                id=shared_fs_name,
                file_system_id=manifest.shared_efs_fs_id,
                security_group=ec2.SecurityGroup.from_security_group_id(
                    scope=self, id="team_sec_group", security_group_id=manifest.shared_efs_sg_id
                ),
            ),
        )

        self.efs_ap: efs.AccessPoint = EfsBuilder.build_file_system_access_point(
            scope=self, team_manifest=team_manifest, shared_fs=self.shared_fs
        )

        self.ecs_cluster = EcsBuilder.build_cluster(
            scope=self, manifest=manifest, team_manifest=team_manifest, vpc=self.i_vpc
        )
        self.ecr_image = EcsBuilder.build_ecr_image(scope=self, manifest=manifest, team_manifest=team_manifest)
        self.ecr_image_spark = EcsBuilder.build_ecr_image_spark(
            scope=self, manifest=manifest, team_manifest=team_manifest
        )
        self.ecs_execution_role = IamBuilder.build_ecs_role(scope=self)
        self.ecs_task_definition = EcsBuilder.build_task_definition(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            ecs_execution_role=self.ecs_execution_role,
            ecs_task_role=self.role_eks_nodegroup,
            file_system=self.shared_fs,
            fs_accesspoint=self.efs_ap,
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
            team_security_group=self.team_security_group,
            subnets=self.i_private_subnets if self.manifest.internet_accessible else self.i_isolated_subnets,
            role=self.container_runner_role,
            scratch_bucket=self.scratch_bucket,
        )
        self.eks_k8s_api = StateMachineBuilder.build_eks_k8s_api_state_machine(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            role=self.container_runner_role,
        )
        self.eks_fargate_runner = StateMachineBuilder.build_eks_run_container_state_machine(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            image=self.ecr_image,
            role=self.container_runner_role,
            node_type="fargate",
        )
        self.eks_ec2_runner = StateMachineBuilder.build_eks_run_container_state_machine(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            image=self.ecr_image,
            role=self.container_runner_role,
            node_type="ec2",
        )

        self.container_runner = LambdaBuilder.build_container_runner(
            scope=self,
            manifest=manifest,
            team_manifest=team_manifest,
            ecs_fargate_runner=self.ecs_fargate_runner,
            eks_fargate_runner=self.eks_fargate_runner,
            eks_ec2_runner=self.eks_ec2_runner,
        )

        self.team_manifest.efs_id = self.shared_fs.file_system_id
        self.team_manifest.efs_ap_id = self.efs_ap.access_point_id
        self.team_manifest.eks_nodegroup_role_arn = self.role_eks_nodegroup.role_arn
        self.team_manifest.scratch_bucket = self.scratch_bucket.bucket_name
        self.team_manifest.ecs_cluster_name = self.ecs_cluster.cluster_name
        self.team_manifest.container_runner_arn = self.container_runner.function_arn
        self.team_manifest.eks_k8s_api_arn = self.eks_k8s_api.state_machine_arn
        self.team_manifest.team_kms_key_arn = self.team_kms_key.key_arn
        self.team_manifest.team_security_group_id = self.team_security_group.security_group_id

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
        ssm_profile_name = f"/orbit/{self.manifest.name}/teams/{self.team_manifest.name}/user/profiles"
        self.user_profiles: ssm.StringParameter = ssm.StringParameter(
            scope=self,
            id=ssm_profile_name,
            string_value="[]",
            type=ssm.ParameterType.STRING,
            description="Team additional profiles created by the team users",
            parameter_name=ssm_profile_name,
            simple_name=False,
            tier=ssm.ParameterTier.INTELLIGENT_TIERING,
        )


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 4:
        manifest: Manifest
        if sys.argv[1] == "manifest":
            filename: str = sys.argv[2]
            manifest = Manifest(filename=filename, env=None, region=None)
        elif sys.argv[1] == "env":
            env: str = sys.argv[2]
            manifest = Manifest(filename=None, env=env, region=None)
        else:
            raise ValueError(f"Unexpected argv[1] ({len(sys.argv)}) - {sys.argv}.")
        team_name: str = sys.argv[3]
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    manifest.fillup()

    changes: changeset.Changeset = changeset.read_changeset_file(manifest=manifest, filename="changeset.json")
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

    outdir = os.path.join(".orbit.out", manifest.name, "cdk", team_manifest.stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    app = App(outdir=outdir)
    Team(scope=app, id=team_manifest.stack_name, manifest=manifest, team_manifest=team_manifest)
    app.synth(force=True)


if __name__ == "__main__":
    main()
