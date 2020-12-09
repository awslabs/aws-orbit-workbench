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

import json
from typing import List

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_iam as iam
import aws_cdk.core as core
from aws_cdk import aws_lambda

from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.remote_files.cdk import _lambda_path


class LambdaBuilder:
    @staticmethod
    def build_ecs_container_runner(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        ecs_execution_role: iam.Role,
        ecs_task_role: iam.Role,
        ecs_cluster: ecs.Cluster,
        ecs_task_definition: ecs.TaskDefinition,
        efs_security_group: ec2.SecurityGroup,
        subnets: List[ec2.ISubnet],
    ) -> aws_lambda.Function:
        return aws_lambda.Function(
            scope=scope,
            id="ecs_container_runner",
            function_name=f"datamaker-{manifest.name}-{team_manifest.name}-container-runner",
            code=aws_lambda.Code.asset(_lambda_path("container_runner")),
            handler="lambda_source.handler",
            runtime=aws_lambda.Runtime.PYTHON_3_6,
            timeout=core.Duration.minutes(5),
            environment={
                "ROLE": ecs_task_role.role_arn,
                "SECURITY_GROUP": efs_security_group.security_group_id,
                "SUBNETS": json.dumps([s.subnet_id for s in subnets]),
                "TASK_DEFINITION": ecs_task_definition.task_definition_arn,
                "CLUSTER": ecs_cluster.cluster_name,
                "AWS_DATAMAKER_ENV": manifest.name,
                "AWS_DATAMAKER_TEAMSPACE": team_manifest.name,
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
                        "ecs:RunTask",
                    ],
                    resources=[
                        f"arn:{core.Aws.PARTITION}:ecs:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:task-definition/"
                        f"{ecs_task_definition.family}:*"
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "iam:PassRole",
                    ],
                    resources=[ecs_task_role.role_arn, ecs_execution_role.role_arn],
                ),
            ],
        )

    @staticmethod
    def build_eks_describe_cluster(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
    ) -> aws_lambda.Function:
        return aws_lambda.Function(
            scope=scope,
            id="eks_describe_cluster",
            function_name=f"datamaker-{manifest.name}-{team_manifest.name}-eks-describe-cluster",
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

    @staticmethod
    def build_construct_url(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
    ) -> aws_lambda.Function:
        return aws_lambda.Function(
            scope=scope,
            id="construct_rul",
            function_name=f"datamaker-{manifest.name}-{team_manifest.name}-construct-url",
            code=aws_lambda.Code.asset(_lambda_path("construct_url")),
            handler="index.handler",
            runtime=aws_lambda.Runtime.PYTHON_3_6,
            timeout=core.Duration.seconds(10),
        )
