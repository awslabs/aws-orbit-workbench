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

from typing import cast

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_efs as efs
import aws_cdk.aws_iam as iam
import aws_cdk.aws_logs as logs
import aws_cdk.core as core
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest


class EcsBuilder:
    @staticmethod
    def build_cluster(
        scope: core.Construct, manifest: Manifest, team_manifest: TeamManifest, vpc: ec2.Vpc
    ) -> ecs.Cluster:
        return ecs.Cluster(
            scope,
            "ecs_cluster",
            vpc=vpc,
            cluster_name=f"orbit-{manifest.name}-{team_manifest.name}-cluster",
        )

    @staticmethod
    def build_ecr_image(scope: core.Construct, manifest: Manifest, team_manifest: TeamManifest) -> ecs.EcrImage:
        repository_name, tag = team_manifest.construct_ecr_repository_name(manifest.name).split(":")
        repository = ecr.Repository.from_repository_name(
            scope,
            "ecr_repository",
            repository_name=repository_name,
        )
        return cast(ecs.EcrImage, ecs.ContainerImage.from_ecr_repository(repository=repository, tag=tag))

    @staticmethod
    def build_task_definition(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        ecs_execution_role: iam.Role,
        ecs_task_role: iam.Role,
        file_system: efs.FileSystem,
        image: ecs.EcrImage,
    ) -> ecs.TaskDefinition:
        ecs_log_group = logs.LogGroup(
            scope,
            "ecs_log_group",
            log_group_name=f"/orbit/tasks/{manifest.name}/{team_manifest.name}/containers",
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        task_definition = ecs.TaskDefinition(
            scope,
            "ecs_task_definition",
            memory_mib=f"{team_manifest.container_defaults['memory']}",
            cpu=f"{team_manifest.container_defaults['cpu'] * 1024}",
            execution_role=ecs_execution_role,
            task_role=ecs_task_role,
            compatibility=ecs.Compatibility.EC2_AND_FARGATE,
            family=f"orbit-{manifest.name}-{team_manifest.name}-task-definition",
            network_mode=ecs.NetworkMode.AWS_VPC,
            volumes=[
                ecs.Volume(
                    name="team_efs_volume",
                    efs_volume_configuration=ecs.EfsVolumeConfiguration(
                        file_system_id=file_system.file_system_id, transit_encryption="ENABLED"
                    ),
                )
            ],
        )
        container_definition = task_definition.add_container(
            "orbit-runner",
            memory_limit_mib=team_manifest.container_defaults["memory"],
            image=image,
            logging=ecs.LogDriver.aws_logs(
                stream_prefix=f"orbit-{manifest.name}-{team_manifest.name}",
                log_group=ecs_log_group,
            ),
        )
        container_definition.add_mount_points(
            ecs.MountPoint(container_path="/efs", source_volume="team_efs_volume", read_only=False)
        )

        return task_definition
