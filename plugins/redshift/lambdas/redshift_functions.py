#TODO - Add pause and resume boto3 calls



import logging
from datamaker.common.configuration import *
import json
import os
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
ssm = boto3.client('ssm')
from datamaker.common.datamaker_constants import *

import json
import boto3
import logging

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def lambda_handler(event, context):
    redshift = boto3.client(
        'redshift'
    )
    secretsmanager = boto3.client('secretsmanager')
    response = secretsmanager.get_secret_value(SecretId=os.environ['SecretId'])
    passJson = json.loads(response['SecretString'])
    password = passJson['password']
    user = passJson['username']
    clusterIdentifier = event['cluster_name']
    try:
        clusterInfo = redshift.describe_clusters(
            ClusterIdentifier=clusterIdentifier
        )
        LOGGER.error("Cluster already exists")
        if not clusterInfo['Clusters'].isEmpty():
            return {
                'statusCode': "409",
            }

        # Cluster Found with Paused State, resume the cluster.
        if clusterInfo['ClusterStatus'] == "paused":
            resume_response = redshift.resume_cluster(ClusterIdentifier=clusterIdentifier)
            if not resume_response:
                return {
                    'statusCode': "409",
                }
            else:
                return {
                    'statusCode': "200",
                    'cluster_id': resume_response['Cluster']['ClusterIdentifier'],
                    'username': user,
                    'modify_status': resume_response['Cluster']['ModifyStatus']
                }

    except:
        LOGGER.debug("Cluster not found,good, now lets start it")

    database = event['Database'] if 'Database' in event else os.environ['Database']

    response = redshift.create_cluster(
        DBName=database,
        ClusterIdentifier=clusterIdentifier,
        ClusterType=event['ClusterType'] if 'ClusterType' in event else os.environ['ClusterType'],
        NodeType=event['NodeType'] if 'NodeType' in event else os.environ['NodeType'],
        Encrypted=True,
        KmsKeyId=os.environ['kms_key'],
        AutomatedSnapshotRetentionPeriod=0, #Snaphot disabled
        MasterUsername=user,
        MasterUserPassword=password,
        VpcSecurityGroupIds=[ os.environ['RedshiftClusterSecurityGroup']],
        ClusterSubnetGroupName=os.environ['RedshiftClusterSubnetGroup'],
        ClusterParameterGroupName=os.environ['RedshiftClusterParameterGroup'],
        Port=int(event['PortNumber'] if 'PortNumber' in event else os.environ['PortNumber']),
        NumberOfNodes = int(event['Nodes'] if 'Nodes' in event else os.environ['Nodes']),
        PubliclyAccessible = False,
        IamRoles = [os.environ['Role']],
        Tags = [
            {
                'Key': DATAMAKER_PRODUCT_KEY,
                'Value': DATAMAKER_PRODUCT_NAME
            },
            {
                'Key': DATAMAKER_SUBPRODUCT_KEY,
                'Value': DATAMAKER_SUBPRODUCT_REDSHIFT
            },
            {
                'Key': DATAMAKER_ENV,
                'Value': os.environ[DATAMAKER_ENV]
            },
            {
                'Key': DATAMAKER_TEAM_SPACE,
                'Value': os.environ[DATAMAKER_TEAM_SPACE]
            },
            {
                'Key': 'MasterPasswordSecretID',
                'Value': os.environ['SecretId']
            }
        ]
    )

    cluster_id = response['Cluster']['ClusterIdentifier']
    print('cluster created: ', cluster_id)
    return {
        'statusCode': "200",
        'cluster_id': cluster_id,
        'username': user
    }