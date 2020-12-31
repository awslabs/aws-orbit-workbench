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

import aws_cdk.aws_cognito as cognito
import aws_cdk.core as core
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest


class CognitoBuilder:
    @staticmethod
    def build_user_pool_group(
        scope: core.Construct, manifest: Manifest, team_manifest: TeamManifest
    ) -> cognito.CfnUserPoolGroup:
        if manifest.user_pool_id is None:
            raise RuntimeError("Empty manifest.user_pool_id")
        return cognito.CfnUserPoolGroup(
            scope=scope,
            id=f"{team_manifest.name}_group",
            user_pool_id=manifest.user_pool_id,
            group_name=team_manifest.name,
            description=f"{team_manifest.name} users group.",
        )
