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
from typing import TYPE_CHECKING, Any, Dict, cast

import aws_cdk.aws_iam as iam
from aws_cdk.core import Construct, Environment, IConstruct, Stack, Tags
from aws_orbit.plugins.helpers import cdk_handler

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger(__name__)


class Team(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        context: "Context",
        team_context: "TeamContext",
        parameters: Dict[str, Any],
    ) -> None:

        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=context.account_id, region=context.region),
        )
        Tags.of(scope=cast(IConstruct, self)).add(key="Env", value=f"orbit-{context.name}")

        if team_context.eks_pod_role_arn is None:
            raise ValueError("Pod Role arn required")
        team_role = iam.Role.from_role_arn(
            scope=self,
            id="team-role",
            role_arn=team_context.eks_pod_role_arn,
            mutable=True,
        )
        team_role.attach_inline_policy(
            policy=iam.Policy(
                scope=self,
                id="emr_on_eks",
                policy_name="emr_on_eks",
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "emr-containers:StartJobRun",
                            "emr-containers:ListJobRuns",
                            "emr-containers:DescribeJobRun",
                            "emr-containers:CancelJobRun",
                            "emr-containers:TagResource",
                        ],
                        resources=[parameters.get("virtual_arn", "*")],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "logs:Describe*",
                        ],
                        resources=["arn:aws:logs:*:*:*"],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "logs:*",
                        ],
                        resources=[
                            f"arn:aws:logs:{context.region}:{context.account_id}:log-group:/orbit/emr/*",
                            f"arn:aws:logs:{context.region}:{context.account_id}:log-group:/orbit/emr/*:log-stream:*",
                        ],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "emr-containers:Get*",
                            "emr-containers:Describe*",
                            "emr-containers:List*",
                            "elasticmapreduce:CreatePersistentAppUI",
                            "elasticmapreduce:DescribePersistentAppUI",
                            "elasticmapreduce:GetPersistentAppUIPresignedURL",
                        ],
                        resources=["*"],
                    ),
                ],
            )
        )


if __name__ == "__main__":
    cdk_handler(stack_class=Team)
