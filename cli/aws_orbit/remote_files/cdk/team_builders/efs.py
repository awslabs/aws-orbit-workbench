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
import aws_cdk.aws_kms as kms
import aws_cdk.core as core


class EfsBuilder:
    @staticmethod
    def build_file_system(
        scope: core.Construct,
        name: str,
        efs_life_cycle: str,
        vpc: ec2.IVpc,
        efs_security_group: ec2.ISecurityGroup,
        subnets: List[ec2.ISubnet],
        team_kms_key: kms.Key,
    ) -> efs.FileSystem:
        fs_name: str = f"orbit-{name}-fs"
        efs_fs: efs.FileSystem = efs.FileSystem(
            scope=scope,
            id=fs_name,
            file_system_name=fs_name,
            vpc=vpc,
            encrypted=True,
            lifecycle_policy=efs.LifecyclePolicy[efs_life_cycle] if efs_life_cycle else None,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            throughput_mode=efs.ThroughputMode.BURSTING,
            security_group=efs_security_group,
            vpc_subnets=ec2.SubnetSelection(subnets=subnets),
            kms_key=team_kms_key,
        )
        return efs_fs

    @staticmethod
    def build_file_system_access_point(
        scope: core.Construct, team_name: str, shared_fs: efs.FileSystem
    ) -> efs.AccessPoint:
        ap_name: str = f"{team_name}"
        return efs.AccessPoint(
            scope=scope,
            id=ap_name,
            file_system=shared_fs,
            path=f"/{team_name}",
            posix_user=efs.PosixUser(gid="100", uid="1000"),
            create_acl=efs.Acl(owner_gid="100", owner_uid="1000", permissions="770"),
        )
