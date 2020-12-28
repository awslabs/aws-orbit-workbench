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

import aws_cdk.aws_iam as iam
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.core as core
from aws_cdk import aws_lambda

from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.remote_files.cdk import _lambda_path


class LambdaBuilder:
    @staticmethod
    def build_container_runner(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        ecs_fargate_runner: sfn.StateMachine,
        eks_fargate_runner: sfn.StateMachine,
        eks_ec2_runner: sfn.StateMachine,
    ) -> aws_lambda.Function:
        return aws_lambda.Function(
            scope=scope,
            id="container_runner",
            function_name=f"orbit-{manifest.name}-{team_manifest.name}-container-runner",
            code=aws_lambda.Code.asset(_lambda_path("container_runner")),
            handler="index.handler",
            runtime=aws_lambda.Runtime.PYTHON_3_6,
            timeout=core.Duration.minutes(5),
            environment={
                "ECS_FARGATE_STATE_MACHINE_ARN": ecs_fargate_runner.state_machine_arn,
                "EKS_FARGATE_STATE_MACHINE_ARN": eks_fargate_runner.state_machine_arn,
                "EKS_EC2_STATE_MACHINE_ARN": eks_ec2_runner.state_machine_arn,
            },
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ec2:Describe*", "logs:Create*", "logs:PutLogEvents", "logs:Describe*"],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "states:StartExecution",
                    ],
                    resources=[ecs_fargate_runner.state_machine_arn],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "states:GetExecutionHistory",
                    ],
                    resources=[
                        f"arn:{core.Aws.PARTITION}:states:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:"
                        f"execution:{ecs_fargate_runner.state_machine_name}*"
                    ],
                ),
            ],
        )

    @staticmethod
    def get_or_build_eks_describe_cluster(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
    ) -> aws_lambda.Function:
        stack = core.Stack.of(scope)
        lambda_function = cast(aws_lambda.Function, stack.node.try_find_child("eks_describe_cluster"))
        if lambda_function is None:
            lambda_function = aws_lambda.Function(
                scope=stack,
                id="eks_describe_cluster",
                function_name=f"orbit-{manifest.name}-{team_manifest.name}-eks-describe-cluster",
                code=aws_lambda.Code.asset(_lambda_path("eks_describe_cluster")),
                handler="index.handler",
                runtime=aws_lambda.Runtime.PYTHON_3_6,
                timeout=core.Duration.seconds(30),
                initial_policy=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["eks:DescribeCluster"],
                        resources=["*"],
                    )
                ],
            )
        return lambda_function

    @staticmethod
    def get_or_build_construct_url(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
    ) -> aws_lambda.Function:
        stack = core.Stack.of(scope)
        lambda_function = cast(aws_lambda.Function, stack.node.try_find_child("construct_url"))
        if lambda_function is None:
            lambda_function = aws_lambda.Function(
                scope=stack,
                id="construct_url",
                function_name=f"orbit-{manifest.name}-{team_manifest.name}-construct-url",
                code=aws_lambda.Code.asset(_lambda_path("construct_url")),
                handler="index.handler",
                runtime=aws_lambda.Runtime.PYTHON_3_6,
                timeout=core.Duration.seconds(10),
            )
        return lambda_function
