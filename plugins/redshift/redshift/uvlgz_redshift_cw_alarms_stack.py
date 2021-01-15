from aws_cdk import (
    aws_iam as iam,
    aws_events as events,
    aws_lambda as _lambda,
    aws_events_targets as targets,
    aws_sns as sns,
    core
)
import json
import os

class UvlGzRedshiftCWAlertsStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        stack = core.Stack.of(self)
        aws_region = stack.region
        aws_account = stack.account

        current_dir = os.path.dirname(__file__)

        redshift_cw_event_creator_lambda_role = iam.Role(
            self,
            id='redshift-cw-event-role',
            description='Role for the Redshift CW event creator lambda',
            role_name=f'uvl-{core.Aws.REGION}-gz-i-redshift-cw-creator-lambda-role',
            max_session_duration=core.Duration.seconds(3600),
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            inline_policies={
                'AllowLogsAccess': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[        
                                "logs:PutLogEvents",
                                "logs:DescribeLogStreams",
                                "logs:DescribeLogGroups",
                                "logs:CreateLogStream",
                                "logs:CreateLogGroup"
                                ],
                            resources=[f'arn:aws:logs:{aws_region}:{aws_account}:log-group:*']
                                )
                            ]
                        ),
                'AllowCWAccess': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[        
                                "cloudwatch:PutMetricAlarm",
                                "cloudwatch:EnableAlarmActions",
                                "cloudwatch:DeleteAlarms",
                                "cloudwatch:DisableAlarmActions",
                                "cloudwatch:Describe*"
                                ],
                            resources=[f'arn:aws:cloudwatch:{aws_region}:{aws_account}:alarm:*']
                                )
                            ]
                        ),
                'AllowSTSAccess': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[        
                                "sts:GetCallerIdentity"
                                ],
                            resources=['*']
                                )
                            ]
                        )
                         }
            )

        redshift_cw_event_creator_lambda = _lambda.Function(self,'RedshiftCWEventCreator',
            handler='lambda-redshift-cw-event-creator.lambda_handler',
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset(os.path.join(current_dir,'../../uvlgc/lambda/redshift-cw-event-creator')),
            role=redshift_cw_event_creator_lambda_role,
            memory_size=256,
            timeout=core.Duration.seconds(60)
        )


        redshift_cw_create_alarm_event = events.Rule(
            self,
            'cw-alarm-event',
            rule_name='redshift-cw-alarm-creator',
            description='Create CloudWatch alarms for transient clusters to terminate them when idle',
            targets=[targets.LambdaFunction(redshift_cw_event_creator_lambda)],
            event_pattern=events.EventPattern(
                source=['aws.redshift'],
                detail_type=['AWS API Call via CloudTrail'],
                detail={
                    'eventSource': ['redshift.amazonaws.com'],
                    'eventName': ['CreateCluster']
                }
            )
        )

        redshift_terminator_lambda_role = iam.Role(
            self,
            id='redshift-terminator-lambda-role',
            description='Role for the Redshift lambda terminator',
            role_name=f'uvl-{core.Aws.REGION}-gz-i-redshift-terminator-lambda-role',
            max_session_duration=core.Duration.seconds(3600),
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            inline_policies={
                'AllowLogsAccess': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[        
                                "logs:PutLogEvents",
                                "logs:DescribeLogStreams",
                                "logs:DescribeLogGroups",
                                "logs:CreateLogStream",
                                "logs:CreateLogGroup"
                                ],
                            resources=[f'arn:aws:logs:{aws_region}:{aws_account}:log-group:*']
                                )
                            ]
                        ),
                'AllowCloudWatchAccess': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[        
                                "cloudwatch:Describe*",
                                "cloudwatch:Get*",
                                "cloudwatch:DeleteAlarms",
                                "cloudwatch:List*"
                                ],
                            resources=[f'arn:aws:cloudwatch:{aws_region}:{aws_account}:alarm:*']
                                )
                            ]
                        ),
                'AllowRedshiftAccess': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[        
                                "redshift:DeleteClusterSecurityGroup",
                                "redshift:DeleteCluster",
                                "redshift:DeleteClusterSnapshot",
                                "redshift:Describe*"
                                ],
                            resources=[f'arn:aws:redshift:{aws_region}:{aws_account}:cluster:uv-*']
                                )
                            ]
                        )
                         }
            )

        redshift_terminator_lambda = _lambda.Function(self,'RedshiftTerminator',
            handler='lambda-redshift-terminator.lambda_handler',
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset(os.path.join(current_dir,'../../uvlgc/lambda/redshift-cw-event-creator')),
            role=redshift_terminator_lambda_role,
            memory_size=256,
            timeout=core.Duration.seconds(60)
        )

        redshift_terminator_sns_topic = sns.Topic(self, 'RedshiftTerminatorSNSTopic',
        display_name='redshift-terminator-topic',
        topic_name='redshift-terminator-topic'
        )

        redshift_terminator_sns_topic_subscription = sns.Subscription(self, 'RedshiftTerminatorSNSTopicSubscription',
        topic=redshift_terminator_sns_topic,
        protocol=sns.SubscriptionProtocol.LAMBDA,
        endpoint=redshift_terminator_lambda.function_arn
        )

        lambda_sns_resource_policy = redshift_terminator_lambda.add_permission(id='lambda_resource_policy',
                principal=iam.ServicePrincipal(service='sns.amazonaws.com'),
                action='lambda:InvokeFunction',
                source_arn=redshift_terminator_sns_topic.topic_arn
        )

