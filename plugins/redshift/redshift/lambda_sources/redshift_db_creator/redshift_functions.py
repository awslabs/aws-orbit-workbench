import json
import logging
import os
from typing import Any, Dict, Optional

import boto3

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, str]:
    redshift = boto3.client("redshift")
    secretsmanager = boto3.client("secretsmanager")
    response = secretsmanager.get_secret_value(SecretId=os.environ["SecretId"])
    passJson = json.loads(response["SecretString"])
    password = passJson["password"]
    user = passJson["username"]
    clusterIdentifier = event["cluster_name"]
    try:
        clusterInfo = redshift.describe_clusters(ClusterIdentifier=clusterIdentifier)
        LOGGER.error("Cluster already exists")
        if not clusterInfo["Clusters"].isEmpty():
            return {
                "statusCode": "409",
            }
        # Cluster Found with Paused State, resume the cluster.
        if clusterInfo["ClusterStatus"] == "paused":
            resume_response = redshift.resume_cluster(ClusterIdentifier=clusterIdentifier)
            if not resume_response:
                return {
                    "statusCode": "409",
                }
            else:
                return {
                    "statusCode": "200",
                    "cluster_id": resume_response["Cluster"]["ClusterIdentifier"],
                    "username": user,
                    "modify_status": resume_response["Cluster"]["ModifyStatus"],
                }
    except Exception:
        LOGGER.debug("Cluster not found,good, now lets start it")

    database = event["Database"] if "Database" in event else os.environ["Database"]

    response = redshift.create_cluster(
        DBName=database,
        ClusterIdentifier=clusterIdentifier,
        ClusterType=event["ClusterType"] if "ClusterType" in event else os.environ["ClusterType"],
        NodeType=event["NodeType"] if "NodeType" in event else os.environ["NodeType"],
        Encrypted=True,
        KmsKeyId=os.environ["kms_key"],
        AutomatedSnapshotRetentionPeriod=0,  # Snaphot disabled
        MasterUsername=user,
        MasterUserPassword=password,
        VpcSecurityGroupIds=[os.environ["RedshiftClusterSecurityGroup"]],
        ClusterSubnetGroupName=os.environ["RedshiftClusterSubnetGroup"],
        ClusterParameterGroupName=os.environ["RedshiftClusterParameterGroup"],
        Port=int(event["PortNumber"] if "PortNumber" in event else os.environ["PortNumber"]),
        NumberOfNodes=int(event["Nodes"] if "Nodes" in event else os.environ["Nodes"]),
        PubliclyAccessible=False,
        IamRoles=[os.environ["Role"]],
        Tags=[
            {"Key": "Product", "Value": "Orbit"},
            {"Key": "SubProduct", "Value": "Redshift"},
            {"Key": "Env", "Value": os.environ["Env"]},
            {"Key": "TeamSpace", "Value": os.environ["TeamSpace"]},
            {"Key": "MasterPasswordSecretID", "Value": os.environ["SecretId"]},
        ],
    )

    cluster_id = response["Cluster"]["ClusterIdentifier"]
    print("cluster created: ", cluster_id)
    return {"statusCode": "200", "cluster_id": cluster_id, "username": user}
