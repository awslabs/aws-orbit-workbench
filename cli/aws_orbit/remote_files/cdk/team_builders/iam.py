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
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, cast

import aws_cdk.aws_iam as iam
import aws_cdk.aws_kms as kms
import aws_cdk.aws_s3 as s3
import aws_cdk.core as core
import botocore

from aws_orbit.utils import boto3_client

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def process_policies(policy_names, account_id) -> Tuple[List[Any], List[Any]]:  # type: ignore
    iam_client = boto3_client("iam")
    aws_managed_user_policies = []
    orbit_custom_policies = []

    def _check_policy_exists(arn: str) -> bool:
        try:
            iam_client.get_policy(PolicyArn=arn)
            return True
        except iam_client.exceptions.NoSuchEntityException:
            return False

    def _check_for_orbit_tag(policyArn: str) -> bool:
        _logger.info(f"Fetching policy tags for {policyArn}")
        retries = 3
        while retries > 0:
            try:
                response = iam_client.list_policy_tags(PolicyArn=policyArn)
                break
            except iam_client.exceptions.ClientError as ce:
                if ce.response["Error"]["Code"] == "Throttling" and ce.response["Error"]["Message"] == "Rate exceeded":
                    _logger.warning(ce)
                    _logger.info(f"Retrying. Retry count: {4 - retries}")

                    time.sleep(60)
                    retries -= 1

                if retries == 0:
                    raise Exception(ce)

        for tag in response["Tags"]:
            key, value = tag["Key"], tag["Value"]
            if "orbit-available" in key and "true" in value:
                return True
        return False

    for policy_name in policy_names:
        aws_managed_arn = f"arn:aws:iam::aws:policy/{policy_name}"
        customer_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
        _logger.info(f"Checking policy name {policy_name}")
        if _check_policy_exists(aws_managed_arn):
            aws_managed_user_policies.append(policy_name)
            _logger.info(f"Found {policy_name} to be AWS-Managed..adding to build")
        elif _check_policy_exists(customer_arn):
            _logger.info(f"Found {policy_name} to be Customer-Managed...checking name or tag")
            if _check_for_orbit_tag(customer_arn) or "orbit" in policy_name:
                orbit_custom_policies.append(policy_name)
                _logger.info(f"Found {policy_name} to be Customer-Managed and properly tagged/named...adding to build")
            else:
                _logger.info(
                    f"Found {policy_name} to be Customer-Managed BUT not tagged or properly named... NOT added to build"
                )
        else:
            _logger.info(f"Found {policy_name} not to exist...NOT added to build")
    return aws_managed_user_policies, orbit_custom_policies


class IamBuilder:
    @staticmethod
    def build_team_role(
        scope: core.Construct,
        context: "Context",
        team_name: str,
        policy_names: List[str],
        scratch_bucket: s3.IBucket,
        team_kms_key: kms.Key,
        session_timeout: core.Duration,
    ) -> iam.Role:
        env_name = context.name
        partition = core.Aws.PARTITION
        account = core.Aws.ACCOUNT_ID
        region = core.Aws.REGION
        lake_role_name: str = f"orbit-{env_name}-{team_name}-{region}-role"
        role_prefix: str = f"/{context.role_prefix}/" if context.role_prefix else "/"
        kms_keys = [team_kms_key.key_arn]
        scratch_bucket_kms_key = IamBuilder.get_kms_key_scratch_bucket(context=context)
        if scratch_bucket_kms_key:
            kms_keys.append(scratch_bucket_kms_key)

        lake_operational_policy = iam.ManagedPolicy(
            scope=scope,
            id="lake_operational_policy",
            managed_policy_name=f"orbit-{env_name}-{team_name}-{region}-user-access",
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
                        f"{scratch_bucket.bucket_arn}/{team_name}/*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:List*", "s3:Get*", "s3:Put*"],
                    resources=[
                        f"arn:{partition}:s3:::{context.toolkit.s3_bucket}",
                        f"arn:{partition}:s3:::{context.toolkit.s3_bucket}/samples/*",
                        f"arn:{partition}:s3:::{context.toolkit.s3_bucket}/codeseeder/*",
                        f"arn:{partition}:s3:::{context.toolkit.s3_bucket}/teams/{team_name}/*",
                        f"arn:{partition}:s3:::{context.toolkit.s3_bucket}/helm/repositories/env/*",
                        f"arn:{partition}:s3:::{context.toolkit.s3_bucket}/helm/repositories/teams/{team_name}/*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ssm:Get*"],
                    resources=[
                        f"arn:{partition}:ssm:{region}:{account}:parameter/orbit*",
                        f"arn:{partition}:ssm:{region}:{account}:parameter/emr_launch/",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ssm:PutParameter"],
                    resources=[
                        f"arn:{partition}:ssm:{region}:{account}:parameter/orbit/{env_name}/teams/{team_name}/user*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "redshift:GetClusterCredentials",
                        "redshift:CreateClusterUser",
                        "redshift:DeleteCluster",
                    ],
                    resources=[
                        f"arn:{partition}:redshift:{region}:{account}:dbuser:orbit-{env_name}-{team_name}*",
                        f"arn:{partition}:redshift:{region}:{account}:dbuser:orbit-{env_name}-{team_name}*/master",
                        f"arn:{partition}:redshift:{region}:{account}:dbuser:orbit-{env_name}-{team_name}*/defaultdb",
                        f"arn:{partition}:redshift:{region}:{account}:dbname:orbit-{env_name}-{team_name}*/defaultdb",
                        f"arn:{partition}:redshift:{region}:{account}:cluster:orbit-{env_name}-{team_name}*",
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
                    resources=[f"arn:{partition}:iam::{account}:role{role_prefix}{lake_role_name}"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ssm:Describe*",
                        "codeartifact:Describe*",
                        "codeartifact:Get*",
                        "codeartifact:List*",
                        "codeartifact:Read*",
                        "sts:GetServiceBearerToken",
                        "s3:ListAllMyBuckets",
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
                        "glue:Get*",
                        "glue:List*",
                        "glue:Search*",
                        "athena:*",
                        "ecs:Describe*",
                        "ecs:ListTasks",
                        "ec2:Describe*",
                        "redshift:DescribeClusters",
                        "elasticmapreduce:List*",
                        "elasticmapreduce:Get*",
                        "elasticmapreduce:Describe*",
                        "elasticmapreduce:TerminateJobFlows",
                        "elasticmapreduce:AddJobFlowSteps",
                        "sagemaker:*",
                        "databrew:*",
                        "lakeformation:GetDataAccess",
                        "fsx:Describe*",
                        "fsx:List*",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ecr:*",
                    ],
                    resources=[f"arn:{partition}:ecr:{region}:{account}:repository/orbit-{env_name}/users/*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["kms:Encrypt", "kms:Decrypt", "kms:ReEncrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
                    resources=kms_keys,
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "lambda:InvokeFunction",
                    ],
                    resources=[
                        f"arn:{partition}:lambda:{region}:{account}:function:orbit-{env_name}-{team_name}-*",
                        f"arn:{partition}:lambda:{region}:{account}:function:orbit-{env_name}-token-validation",
                        f"arn:{partition}:lambda:{region}:{account}:function:orbit-{env_name}-eks-service-handler",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "cloudformation:DescribeStacks",
                    ],
                    resources=[
                        f"arn:{partition}:cloudformation:{region}:{account}:stack/orbit-{env_name}/*",
                        f"arn:{partition}:cloudformation:{region}:{account}:stack/aws-codeseeder-orbit*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ssm:GetParameters",
                        "ssm:DescribeParameters",
                        "ssm:GetParameter",
                        "ssm:DescribeParameter",
                    ],
                    resources=[
                        f"arn:{partition}:ssm:{region}:{account}:parameter/orbit/{env_name}/teams/{team_name}/*",
                        f"arn:{partition}:ssm:{region}:{account}:parameter/Orbit-Slack-Notifications",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ssm:DeleteParameter",
                        "ssm:DeleteParameters",
                    ],
                    resources=[
                        f"arn:{partition}:ssm:{region}:{account}:parameter/orbit/{env_name}/changeset",
                        f"arn:{partition}:ssm:{region}:{account}:parameter/orbit/{env_name}/manifest",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ssm:DescribeParameters",
                    ],
                    resources=[f"arn:{partition}:ssm:{region}:{account}:*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:Put*"],
                    resources=[
                        f"arn:{partition}:s3:::{context.toolkit.s3_bucket}",
                        f"arn:{partition}:s3:::{context.toolkit.s3_bucket}/cli/remote/*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                    resources=[
                        f"arn:{partition}:codebuild:{region}:{account}:project/orbit-{env_name}",
                        f"arn:{partition}:codebuild:{region}:{account}:project/codeseeder-orbit",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                        "logs:DescribeLogStreams",
                        "logs:PutLogEvents",
                    ],
                    resources=[
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/codebuild/orbit-{env_name}:log-stream:*",  # noqa
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/codebuild/codeseeder-orbit:log-stream:*",  # noqa
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws-glue-databrew/*:log-stream:*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:List*",
                        "logs:Describe*",
                        "logs:StartQuery",
                        "logs:StopQuery",
                        "logs:Get*",
                        "logs:Filter*",
                        "events:*",
                    ],
                    resources=[
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/codebuild/orbit-{env_name}*:log-stream:*",  # noqa
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/codebuild/codeseeder-orbit:log-stream:*",  # noqa
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws-glue-databrew/*:log-stream:*",
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/sagemaker/*",
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/sagemaker/*:log-stream:*",
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws/eks/orbit*",
                        f"arn:{partition}:events:{region}:{account}:rule/orbit-{env_name}-{team_name}-*",
                        f"arn:{partition}:logs:{region}:{account}:log-group:/aws-glue-databrew/*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ecr:InitiateLayerUpload",
                    ],
                    resources=[
                        f"arn:{partition}:ecr:{region}:{account}:repository/*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "eks:DescribeCluster",
                    ],
                    resources=[
                        f"arn:{partition}:eks:{region}:{account}:cluster/orbit-{env_name}",
                    ],
                ),
            ],
        )

        managed_policies = [
            lake_operational_policy,
            # For EKS
            iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKS_CNI_Policy"),
        ]

        # Parse list to IAM policies
        # First check if the policies are AWS managed or not, and if they have a tag
        aws_policies, customer_policies = process_policies(policy_names=policy_names, account_id=context.account_id)

        aws_managed_user_policies = [
            iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name=policy_name)
            for policy_name in aws_policies
        ]

        orbit_custom_policies = [
            iam.ManagedPolicy.from_managed_policy_name(scope=scope, id=policy_name, managed_policy_name=policy_name)
            for policy_name in customer_policies
        ]

        managed_policies = (
            managed_policies + cast(List[object], aws_managed_user_policies) + cast(List[object], orbit_custom_policies)
        )

        role = iam.Role(
            scope=scope,
            id=f"lakerole-for-{env_name}-{team_name}",
            role_name=lake_role_name,
            assumed_by=cast(
                iam.IPrincipal,
                iam.CompositePrincipal(
                    iam.ServicePrincipal("ec2.amazonaws.com"),
                    iam.ServicePrincipal("glue.amazonaws.com"),
                    iam.ServicePrincipal("sagemaker.amazonaws.com"),
                    iam.ServicePrincipal("redshift.amazonaws.com"),
                    iam.ServicePrincipal("codepipeline.amazonaws.com"),
                    iam.ServicePrincipal("codebuild.amazonaws.com"),
                    iam.ServicePrincipal("personalize.amazonaws.com"),
                    iam.ServicePrincipal("databrew.amazonaws.com"),
                ),
            ),
            managed_policies=cast(Optional[Sequence[iam.IManagedPolicy]], managed_policies),
            max_session_duration=session_timeout,
        )
        if role.assume_role_policy:
            role.assume_role_policy.add_statements(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["sts:AssumeRoleWithWebIdentity"],
                    principals=[
                        cast(
                            iam.IPrincipal,
                            iam.FederatedPrincipal(
                                federated=f"arn:{partition}:iam::{account}:oidc-provider/{context.eks_oidc_provider}",
                                conditions={
                                    "StringLike": {
                                        f"{context.eks_oidc_provider}:sub": f"system:serviceaccount:{team_name}*:*"
                                    }
                                },
                            ),
                        )
                    ],
                ),
            )
        return role

    @staticmethod
    def get_kms_key_scratch_bucket(context: "Context") -> Optional[str]:
        if not context.scratch_bucket_arn:
            return None
        bucket_name = context.scratch_bucket_arn.split(":::")[1]
        _logger.debug(f"Getting KMS Key for scratch bucket: {bucket_name}")
        try:
            s3_client = boto3_client("s3")
            encryption = cast(
                Dict[str, Any],
                s3_client.get_bucket_encryption(Bucket=bucket_name),
            )
            if (
                "ServerSideEncryptionConfiguration" not in encryption
                or "Rules" not in encryption["ServerSideEncryptionConfiguration"]
            ):
                return None
            for r in encryption["ServerSideEncryptionConfiguration"]["Rules"]:
                if (
                    "ApplyServerSideEncryptionByDefault" in r
                    and "SSEAlgorithm" in r["ApplyServerSideEncryptionByDefault"]
                    and r["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] == "aws:kms"
                ):
                    return cast(str, r["ApplyServerSideEncryptionByDefault"]["KMSMasterKeyID"])
            return None
        except botocore.exceptions.ClientError as e:
            if "ServerSideEncryptionConfigurationNotFoundError" in str(e):
                return None
            raise e
