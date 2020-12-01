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

import aws_cdk.aws_iam as iam
import aws_cdk.aws_s3 as s3
import aws_cdk.core as core

from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest


class IamBuilder:
    @staticmethod
    def build_team_role(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        policy_name: str,
        scratch_bucket: s3.Bucket,
    ) -> iam.Role:
        env_name = manifest.name
        team_name = team_manifest.name
        partition = core.Aws.PARTITION
        account = core.Aws.ACCOUNT_ID
        region = core.Aws.REGION

        lake_role_name: str = f"datamaker-{env_name}-{team_name}-role"
        code_artifact_user_policy = iam.ManagedPolicy(
            scope=scope,
            id="code_artifact_user",
            managed_policy_name=f"datamaker-{env_name}-{team_name}-ca-access",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "codeartifact:DescribePackageVersion",
                        "codeartifact:DescribeRepository",
                        "codeartifact:GetPackageVersionReadme",
                        "codeartifact:GetRepositoryEndpoint",
                        "codeartifact:ListPackages",
                        "codeartifact:ListPackageVersions",
                        "codeartifact:ListPackageVersionAssets",
                        "codeartifact:ListPackageVersionDependencies",
                        "codeartifact:ReadFromRepository",
                        "codeartifact:GetDomainPermissionsPolicy",
                        "codeartifact:ListRepositoriesInDomain",
                        "codeartifact:GetAuthorizationToken",
                        "codeartifact:DescribeDomain",
                        "codeartifact:CreateRepository",
                        "sts:GetServiceBearerToken",
                    ],
                    resources=["*"],
                )
            ],
        )
        lake_operational_policy = iam.ManagedPolicy(
            scope=scope,
            id="lake_operational_policy",
            managed_policy_name=f"datamaker-{env_name}-{team_name}-user-access",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:*",
                    ],
                    resources=[
                        f"arn:{partition}:s3:::sagemaker-{region}-{account}",
                        f"arn:{partition}:s3:::sagemaker-{region}-{account}/*",
                        scratch_bucket.bucket_arn,
                        f"{scratch_bucket.bucket_arn}/*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:CreateBucket"],
                    resources=[f"arn:{partition}:s3:::sagemaker*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ssm:Describe*", "ssm:Get*"],
                    resources=[
                        f"arn:{partition}:ssm:{region}:{account}:parameter/datamaker*",
                        f"arn:{partition}:ssm:{region}:{account}:parameter/emr_launch/",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "redshift:GetClusterCredentials",
                        "redshift:CreateClusterUser",
                    ],
                    resources=[
                        f"arn:{partition}:redshift:{region}:{account}:dbuser:{env_name}-{team_name}*",
                        f"arn:{partition}:redshift:{region}:{account}:dbuser:{env_name}-{team_name}*/master",
                        f"arn:{partition}:redshift:{region}:{account}:dbuser:{env_name}-{team_name}*/defaultdb",
                        f"arn:{partition}:redshift:{region}:{account}:dbname:{env_name}-{team_name}*/defaultdb",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "sns:*",
                    ],
                    resources=[
                        f"arn:{partition}:sns:{region}:{account}:{env_name}-{team_name}*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["iam:PassRole"],
                    resources=[f"arn:{partition}:iam::{account}:role/{lake_role_name}"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["sagemaker:StopNotebookInstance"],
                    resources=[
                        f"arn:{partition}:sagemaker:{region}:{account}:notebook-instance/"
                        f"datamaker-{env_name}-{team_name}*"
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "lambda:List*",
                        "lambda:Get*",
                        "iam:List*",
                        "tag:GetResources",
                        "ecr:Get*",
                        "ecr:List*",
                        "ecr:Describe*",
                        "ecr:BatchGetImage",
                        "ecr:BatchCheckLayerAvailability",
                        "cloudwatch:PutMetricData",
                        "redshift:DescribeClusters",
                        "states:List*",
                        "states:Get*",
                        "states:Describe*",
                        "logs:*",
                        "glue:Get*",
                        "glue:CreateDatabase",
                        "glue:DeleteDatabase",
                        "glue:List*",
                        "glue:Search*",
                        "athena:*",
                        "events:*",
                        "ecs:Describe*",
                        "ecs:ListTasks",
                        "ec2:Describe*",
                        "redshift:DescribeClusters",
                        "elasticmapreduce:List*",
                        "elasticmapreduce:Get*",
                        "elasticmapreduce:Describe*",
                        "elasticmapreduce:TerminateJobFlows",
                        "elasticmapreduce:AddJobFlowSteps",
                        "sagemaker:List*",
                        "sagemaker:Get*",
                        "personalize:*",
                        "sagemaker:Describe*",
                        "sagemaker:CreateModel",
                        "sagemaker:DeleteModelPackage",
                        "sagemaker:UpdateEndpointWeightsAndCapacities",
                        "sagemaker:DeleteAlgorithm",
                        "sagemaker:Search",
                        "sagemaker:UpdateWorkteam",
                        "sagemaker:UpdateNotebookInstanceLifecycleConfig",
                        "sagemaker:DeleteModel",
                        "sagemaker:CreateModelPackage",
                        "sagemaker:DeleteWorkteam",
                        "sagemaker:CreateEndpoint",
                        "sagemaker:CreateEndpointConfig",
                        "sagemaker:RenderUiTemplate",
                        "sagemaker:StopTransformJob",
                        "sagemaker:CreateLabelingJob",
                        "sagemaker:DeleteEndpointConfig",
                        "sagemaker:CreateAlgorithm",
                        "sagemaker:CreateTrainingJob",
                        "sagemaker:StopHyperParameterTuningJob",
                        "sagemaker:DeleteEndpoint",
                        "sagemaker:CreateTransformJob",
                        "sagemaker:InvokeEndpoint",
                        "sagemaker:CreateWorkteam",
                        "sagemaker:StopLabelingJob",
                        "sagemaker:UpdateEndpoint",
                        "sagemaker:CreateCompilationJob",
                        "sagemaker:StopCompilationJob",
                        "sagemaker:CreateHyperParameterTuningJob",
                        "lakeformation:GetDataAccess",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:ListTagsLogGroup",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams",
                        "logs:DescribeSubscriptionFilters",
                        "logs:StartQuery",
                        "logs:GetLogEvents",
                        "logs:DescribeMetricFilters",
                        "logs:FilterLogEvents",
                        "logs:GetLogGroupFields",
                    ],
                    resources=[
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/sagemaker/*",
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/sagemaker/*:log-stream:*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:DescribeQueries",
                        "logs:DescribeExportTasks",
                        "logs:GetLogRecord",
                        "logs:GetQueryResults",
                        "logs:StopQuery",
                        "logs:TestMetricFilter",
                        "logs:DescribeResourcePolicies",
                        "logs:GetLogDelivery",
                        "logs:DescribeDestinations",
                        "logs:ListLogDeliveries",
                    ],
                    resources=["*"],
                ),
            ],
        )

        glue_policy = iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
        ssm_manage_policy = iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        eks_policies = [
            iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSWorkerNodePolicy"),
            iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKS_CNI_Policy"),
            iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEC2ContainerRegistryReadOnly"),
        ]

        managed_policies = [
            lake_operational_policy,
            code_artifact_user_policy,
            glue_policy,
            ssm_manage_policy,
        ] + eks_policies

        user_policies = [iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name=policy_name)]

        managed_policies = managed_policies + user_policies

        return iam.Role(
            scope=scope,
            id=lake_role_name,
            role_name=lake_role_name,
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com"),
                iam.ServicePrincipal("glue.amazonaws.com"),
                iam.ServicePrincipal("sagemaker.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                iam.ServicePrincipal("redshift.amazonaws.com"),
                iam.ServicePrincipal("codepipeline.amazonaws.com"),
                iam.ServicePrincipal("personalize.amazonaws.com"),
            ),
            managed_policies=managed_policies,
        )

    @staticmethod
    def build_ecs_role(scope: core.Construct) -> iam.Role:
        return iam.Role(
            scope,
            "ecs_execution_role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ],
        )
