# import json
# import os
# from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast
#
# from aws_cdk import aws_events as events
# from aws_cdk import aws_events_targets as targets
# from aws_cdk import aws_iam as iam
# from aws_cdk import aws_lambda as aws_lambda
# from aws_cdk import aws_sns as sns
# from aws_cdk import core
# from aws_cdk.core import Construct, Environment, Stack, Tags
# from aws_orbit.plugins.helpers import cdk_handler
#
# from . import _lambda_path
#
# if TYPE_CHECKING:
#     from aws_orbit.manifest import Manifest
#     from aws_orbit.manifest.team import MANIFEST_TEAM_TYPE, TeamManifest
#
#
# class RedshiftCWAlertsStack(core.Stack):
#     def __init__(
#         self, scope: Construct, id: str, manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]
#     ) -> None:
#
#         super().__init__(
#             scope=scope,
#             id=id,
#             stack_name=id,
#             env=Environment(account=manifest.account_id, region=manifest.region),
#         )
#         Tags.of(scope=self).add(key="Env", value=f"orbit-{manifest.name}")
#
#         aws_region = team_manifest.manifest.region
#         aws_account = team_manifest.manifest.account_id
#         aws_partition = core.Aws.PARTITION
#         code = aws_lambda.Code.asset(_lambda_path(path="redshift_cw_event_creator"))
#
#         current_dir = os.path.dirname(__file__)
#
#         redshift_cw_event_creator_lambda_role = iam.Role(
#             self,
#             id="orbit-redshift-cw-event-role",
#             # id='redshift-cw-event-role',
#             description="Role for the Redshift CW event creator lambda",
#             # role_name=f'uvl-{core.Aws.REGION}-gz-i-redshift-cw-creator-lambda-role',
#             max_session_duration=core.Duration.seconds(3600),
#             assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
#             inline_policies={
#                 "AllowLogsAccess": iam.PolicyDocument(
#                     statements=[
#                         iam.PolicyStatement(
#                             effect=iam.Effect.ALLOW,
#                             actions=[
#                                 "logs:PutLogEvents",
#                                 "logs:DescribeLogStreams",
#                                 "logs:DescribeLogGroups",
#                                 "logs:CreateLogStream",
#                                 "logs:CreateLogGroup",
#                             ],
#                             resources=[f"arn:{aws_partition}:logs:{aws_region}:{aws_account}:log-group:*"],
#                         )
#                     ]
#                 ),
#                 "AllowCWAccess": iam.PolicyDocument(
#                     statements=[
#                         iam.PolicyStatement(
#                             effect=iam.Effect.ALLOW,
#                             actions=[
#                                 "cloudwatch:PutMetricAlarm",
#                                 "cloudwatch:EnableAlarmActions",
#                                 "cloudwatch:DeleteAlarms",
#                                 "cloudwatch:DisableAlarmActions",
#                                 "cloudwatch:Describe*",
#                             ],
#                             resources=[f"arn:{aws_partition}:cloudwatch:{aws_region}:{aws_account}:alarm:*"],
#                         )
#                     ]
#                 ),
#                 "AllowSTSAccess": iam.PolicyDocument(
#                     statements=[
#                         iam.PolicyStatement(effect=iam.Effect.ALLOW, actions=["sts:GetCallerIdentity"],
#                         resources=["*"])
#                     ]
#                 ),
#             },
#         )
#
#         redshift_cw_event_creator_lambda = aws_lambda.Function(
#             self,
#             "RedshiftCWEventCreator",
#             handler="lambda_redshift_cw_event_creator.lambda_handler",
#             runtime=aws_lambda.Runtime.PYTHON_3_8,
#             # code=aws_lambda.Code.asset(os.path.join(current_dir,'../../uvlgc/lambda/redshift-cw-event-creator')),
#             code=code,
#             role=redshift_cw_event_creator_lambda_role,
#             memory_size=256,
#             timeout=core.Duration.seconds(60),
#         )
#
#         redshift_cw_create_alarm_event = events.Rule(
#             self,
#             "cw-alarm-event",
#             rule_name="redshift-cw-alarm-creator",
#             description="Create CloudWatch alarms for transient clusters to terminate them when idle",
#             targets=[targets.LambdaFunction(redshift_cw_event_creator_lambda)],
#             event_pattern=events.EventPattern(
#                 source=["aws.redshift"],
#                 detail_type=["AWS API Call via CloudTrail"],
#                 detail={"eventSource": ["redshift.amazonaws.com"], "eventName": ["CreateCluster"]},
#             ),
#         )
#
#         redshift_terminator_lambda_role = iam.Role(
#             self,
#             id="redshift-terminator-lambda-role",
#             description="Role for the Redshift lambda terminator",
#             # role_name=f'uvl-{core.Aws.REGION}-gz-i-redshift-terminator-lambda-role',
#             max_session_duration=core.Duration.seconds(3600),
#             assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
#             inline_policies={
#                 "AllowLogsAccess": iam.PolicyDocument(
#                     statements=[
#                         iam.PolicyStatement(
#                             effect=iam.Effect.ALLOW,
#                             actions=[
#                                 "logs:PutLogEvents",
#                                 "logs:DescribeLogStreams",
#                                 "logs:DescribeLogGroups",
#                                 "logs:CreateLogStream",
#                                 "logs:CreateLogGroup",
#                             ],
#                             resources=[f"arn:{aws_partition}:logs:{aws_region}:{aws_account}:log-group:*"],
#                         )
#                     ]
#                 ),
#                 "AllowCloudWatchAccess": iam.PolicyDocument(
#                     statements=[
#                         iam.PolicyStatement(
#                             effect=iam.Effect.ALLOW,
#                             actions=[
#                                 "cloudwatch:Describe*",
#                                 "cloudwatch:Get*",
#                                 "cloudwatch:DeleteAlarms",
#                                 "cloudwatch:List*",
#                             ],
#                             resources=[f"arn:{aws_partition}:cloudwatch:{aws_region}:{aws_account}:alarm:*"],
#                         )
#                     ]
#                 ),
#                 "AllowRedshiftAccess": iam.PolicyDocument(
#                     statements=[
#                         iam.PolicyStatement(
#                             effect=iam.Effect.ALLOW,
#                             actions=[
#                                 "redshift:DeleteClusterSecurityGroup",
#                                 "redshift:DeleteCluster",
#                                 "redshift:DeleteClusterSnapshot",
#                                 "redshift:Describe*",
#                             ],
#                             resources=[f"arn:{aws_partition}:redshift:{aws_region}:{aws_account}:cluster:uv-*"],
#                         )
#                     ]
#                 ),
#             },
#         )
#
#         redshift_terminator_lambda = aws_lambda.Function(
#             self,
#             "RedshiftTerminator",
#             handler="lambda_redshift_terminator.lambda_handler",
#             runtime=aws_lambda.Runtime.PYTHON_3_8,
#             # code=aws_lambda.Code.asset(os.path.join(current_dir,'../../uvlgc/lambda/redshift-cw-event-creator')),
#             code=code,
#             role=redshift_terminator_lambda_role,
#             memory_size=256,
#             timeout=core.Duration.seconds(60),
#         )
#
#         redshift_terminator_sns_topic = sns.Topic(
#             self,
#             "RedshiftTerminatorSNSTopic",
#             display_name="redshift-terminator-topic",
#             topic_name="redshift-terminator-topic",
#         )
#
#         redshift_terminator_sns_topic_subscription = sns.Subscription(
#             self,
#             "RedshiftTerminatorSNSTopicSubscription",
#             topic=redshift_terminator_sns_topic,
#             protocol=sns.SubscriptionProtocol.LAMBDA,
#             endpoint=redshift_terminator_lambda.function_arn,
#         )
#
#         lambda_sns_resource_policy = redshift_terminator_lambda.add_permission(
#             id="lambda_resource_policy",
#             principal=iam.ServicePrincipal(service="sns.amazonaws.com"),
#             action="lambda:InvokeFunction",
#             source_arn=redshift_terminator_sns_topic.topic_arn,
#         )
#
#
# if __name__ == "__main__":
#     cdk_handler(stack_class=RedshiftCWAlertsStack)
