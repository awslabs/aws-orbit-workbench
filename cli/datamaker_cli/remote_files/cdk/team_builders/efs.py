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

from typing import List

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_efs as efs
import aws_cdk.core as core

from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest


class EfsBuilder:
    @staticmethod
    def build_file_system(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        vpc: ec2.Vpc,
        efs_security_group: ec2.ISecurityGroup,
        subnets: List[ec2.ISubnet],
    ) -> efs.FileSystem:
        name: str = f"datamaker-{manifest.name}-{team_manifest.name}-fs"
        return efs.FileSystem(
            scope=scope,
            id=name,
            file_system_name=name,
            vpc=vpc,
            encrypted=True,
            lifecycle_policy=efs.LifecyclePolicy[team_manifest.efs_life_cycle]
            if team_manifest.efs_life_cycle
            else None,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            throughput_mode=efs.ThroughputMode.BURSTING,
            security_group=efs_security_group,
            vpc_subnets=ec2.SubnetSelection(subnets=subnets),
        )
