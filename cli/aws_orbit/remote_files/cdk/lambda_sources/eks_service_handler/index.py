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
import os
from typing import Any, Dict, List, Optional, Union, cast

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION: str = os.environ["REGION"]


def get_nodegroups(cluster_name: str):
    return_response: List[Dict[str, Dict[str, str]]] = []
    eks_client = boto3.client("eks")
    try:
        nodegroups_response = eks_client.list_nodegroups(clusterName=cluster_name)
        for nodegroup_name in nodegroups_response["nodegroups"]:
            nodegroup_details = eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup_name)
            if "nodegroup" in nodegroup_details:
                nodegroup = nodegroup_details["nodegroup"]
                nodegroup_dict = {
                    nodegroup_name: {
                        "instance_types": nodegroup["instanceTypes"],
                        "scaling_config": nodegroup["scalingConfig"],
                        "status": nodegroup["status"],
                        "capacity_type": nodegroup["capacityType"],
                    }
                }
                return_response.append(nodegroup_dict)
    except Exception as ekse:
        logger.error("Error describing cluster %s nodegroups: %s", cluster_name, ekse)
    return return_response


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Union[str, int]]:
    nodegroups: List[Dict[str, Dict[str, str]]] = []
    if "cluster_name" in event:
        cluster_name = event["cluster_name"]
        nodegroups: List[Dict[str, Dict[str, str]]] = get_nodegroups(token=cluster_name)
    logger.debug(f"get_nodegroup({cluster_name})={nodegroups}")
    return nodegroups
