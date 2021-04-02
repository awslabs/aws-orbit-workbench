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
from typing import Any, Dict, Optional, cast

from aws_orbit.models.manifest import ManagedNodeGroupManifest
from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def get_nodegroup_autoscaling_group(cluster_name: str, nodegroup_name: str) -> Optional[Dict[str, Any]]:
    _logger.debug(f"Getting AutoScaling Group for Cluster: {cluster_name}, NodeGroup: {nodegroup_name}")

    client = boto3_client("autoscaling")
    paginator = client.get_paginator("describe_auto_scaling_groups")

    for response in paginator.paginate():
        for asg in response["AutoScalingGroups"]:
            found_cluster_tag = False
            found_nodegroup_tag = False
            for tag in asg["Tags"]:
                if tag["Key"] == "eks:cluster-name" and tag["Value"] == cluster_name:
                    found_cluster_tag = True
                if tag["Key"] == "eks:nodegroup-name" and tag["Value"] == nodegroup_name:
                    found_nodegroup_tag = True

            if found_cluster_tag and found_nodegroup_tag:
                _logger.debug(f"Found AutoScaling Group: {asg['AutoScalingGroupName']}")
                return cast(Dict[str, Any], asg)

    return None


def update_nodegroup_autoscaling_group(cluster_name: str, nodegroup_manifest: ManagedNodeGroupManifest) -> None:
    _logger.debug(f"Updating AutoScaling Group for Cluster: {cluster_name}, NodeGroup: {nodegroup_manifest.name}")
    _logger.debug(
        f"DesiredCapacity: {nodegroup_manifest.nodes_num_desired}, Min: {nodegroup_manifest.nodes_num_min}, "
        f"Max: {nodegroup_manifest.nodes_num_max}"
    )
    asg = get_nodegroup_autoscaling_group(cluster_name=cluster_name, nodegroup_name=nodegroup_manifest.name)

    if not asg:
        _logger.debug(f"No AutoScaling Group found for Cluster: {cluster_name}, NodeGroup: {nodegroup_manifest.name}")
        return

    client = boto3_client("autoscaling")
    client.update_auto_scaling_group(
        AutoScalingGroupName=asg["AutoScalingGroupName"],
        MinSize=nodegroup_manifest.nodes_num_min,
        MaxSize=nodegroup_manifest.nodes_num_max,
        DesiredCapacity=nodegroup_manifest.nodes_num_desired,
    )
