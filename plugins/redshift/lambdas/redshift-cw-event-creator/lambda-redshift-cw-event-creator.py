import boto3
import json
import os

region = os.environ['AWS_REGION']

sts_client = boto3.client("sts")

account_id = sts_client.get_caller_identity()["Account"]

cloudwatch_client = boto3.client('cloudwatch')

def lambda_handler(event, context):

    cluster_identifier = event['detail']['responseElements']['clusterIdentifier']

    print(cluster_identifier)
    
    alarm_name = cluster_identifier + '-redshift-cluster-idle-alarm'

    cloudwatch_alarm = cloudwatch_client.put_metric_alarm(
        AlarmName=alarm_name,
        AlarmDescription='Triggers an alarm for transient Redshift clusters that are idel',
        ActionsEnabled=True,
        AlarmActions=[f'arn:aws:sns:{region}:{account_id}:redshift-terminator-topic'],
        MetricName='DatabaseConnections',
        Namespace='AWS/Redshift',
        Statistic='Average',
        Dimensions=[
        {
            'Name': 'ClusterIdentifier',
            'Value': cluster_identifier
        },
    ],
        Period=43200,
        EvaluationPeriods=2,
        DatapointsToAlarm=2,
        Threshold=0,
        ComparisonOperator='LessThanOrEqualToThreshold',
        TreatMissingData='missing'
    )