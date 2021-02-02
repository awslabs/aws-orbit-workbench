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


class CognitoBuilder:
    @staticmethod
    def build_user_pool_group(scope: core.Construct, user_pool_id: str, team_name: str) -> cognito.CfnUserPoolGroup:
        return cognito.CfnUserPoolGroup(
            scope=scope,
            id=f"{team_name}_group",
            user_pool_id=user_pool_id,
            group_name=team_name,
            description=f"{team_name} users group.",
        )
