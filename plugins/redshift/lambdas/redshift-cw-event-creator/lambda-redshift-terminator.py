import json
import boto3

redshift_client = boto3.client("redshift")

cloudwatch_client = boto3.client('cloudwatch')

def lambda_handler(event, context):
    
    raw_event = event['Records'][0]['Sns']['Message']
    print(raw_event)
    
    message = json.loads(raw_event)
    
    cluster_identifier = message['Trigger']['Dimensions'][0]['value']

    alarm_name = cluster_identifier + '-redshift-cluster-idle-alarm'
    
    print(cluster_identifier)
    
    cluster = redshift_client.describe_clusters(
        ClusterIdentifier=cluster_identifier,
        TagKeys=[
            'Product',
        ],
        TagValues=[
            'DataMaker',
        ]
    )

    print(cluster)
    
    cluster_tag = str(cluster['Clusters'][0]['Tags'])
    print(cluster_tag)
    
    
    matching_tag = "DataMaker"
    
    if matching_tag in cluster_tag:
        delete_cluster = redshift_client.delete_cluster(
        ClusterIdentifier=cluster_identifier,
        SkipFinalClusterSnapshot=False,
        FinalClusterSnapshotIdentifier=cluster_identifier,
        FinalClusterSnapshotRetentionPeriod=10
        )

        delete_cloudwatch_alarm = cloudwatch_client.delete_alarms(
        AlarmNames=[alarm_name]
        )
    else:
        print("DataMaker tag not found")