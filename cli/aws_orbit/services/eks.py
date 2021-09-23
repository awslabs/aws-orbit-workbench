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
from typing import Any, Dict, List, Optional, cast

from botocore.waiter import WaiterModel, create_waiter_with_client

from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


DELAY = 10
MAX_ATTEMPTS = 60
WAITER_CONFIG = {
    "version": 2,
    "waiters": {
        "FargateProfileCreated": {
            "operation": "DescribeFargateProfile",
            "delay": DELAY,
            "maxAttempts": MAX_ATTEMPTS,
            "acceptors": [
                {"matcher": "path", "expected": "ACTIVE", "argument": "fargateProfile.status", "state": "success"},
                {"matcher": "path", "expected": "CREATING", "argument": "fargateProfile.status", "state": "retry"},
                {
                    "matcher": "path",
                    "expected": "CREATE_FAILED",
                    "argument": "fargateProfile.status",
                    "state": "failure",
                },
            ],
        },
        "FargateProfileDeleted": {
            "operation": "DescribeFargateProfile",
            "delay": DELAY,
            "maxAttempts": MAX_ATTEMPTS,
            "acceptors": [
                {"matcher": "error", "expected": "ResourceNotFoundException", "state": "success"},
                {"matcher": "path", "expected": "DELETING", "argument": "fargateProfile.status", "state": "retry"},
                {
                    "matcher": "path",
                    "expected": "DELETE_FAILED",
                    "argument": "fargateProfile.status",
                    "state": "failure",
                },
            ],
        },
    },
}


def describe_fargate_profile(profile_name: str, cluster_name: str) -> Optional[Dict[str, Any]]:
    _logger.debug(f"Describing Fargate Profile: {cluster_name} - {profile_name}")
    eks_client = boto3_client("eks")

    try:
        return cast(
            Dict[str, Any],
            eks_client.describe_fargate_profile(
                fargateProfileName=profile_name,
                clusterName=cluster_name,
            ),
        )
    except eks_client.exceptions.ResourceNotFoundException:
        return None


def describe_cluster(
    cluster_name: str,
) -> Optional[Dict[str, Any]]:
    _logger.debug(f"Describing Cluster: {cluster_name}")
    eks_client = boto3_client("eks")

    try:
        return cast(Dict[str, Any], eks_client.describe_cluster(name=cluster_name))
    except eks_client.exceptions.ResourceNotFoundException:
        return None


def describe_nodegroup(cluster_name: str, nodegroup_name: str) -> Optional[Dict[str, Any]]:
    _logger.debug(f"Describing NodeGroup: {nodegroup_name}")
    eks_client = boto3_client("eks")

    try:
        return cast(
            Dict[str, Any], eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup_name)
        )
    except eks_client.exceptions.ResourceNotFoundException:
        return None


def create_fargate_profile(
    profile_name: str,
    cluster_name: str,
    role_arn: str,
    subnets: List[str],
    namespaces: List[str],
    selector_labels: Optional[Dict[str, Any]] = None,
) -> None:
    _logger.debug(f"Creating EKS Fargate Profile: {profile_name}")

    if describe_fargate_profile(profile_name=profile_name, cluster_name=cluster_name) is not None:
        _logger.debug(f"EKS Fargate Profile already exists: {profile_name}")
        return

    selectors = [{"namespace": namespace, "labels": selector_labels} for namespace in namespaces]

    eks_client = boto3_client("eks")
    eks_client.create_fargate_profile(
        fargateProfileName=profile_name,
        clusterName=cluster_name,
        podExecutionRoleArn=role_arn,
        subnets=subnets,
        selectors=selectors,
    )

    waiter_model = WaiterModel(WAITER_CONFIG)
    waiter = create_waiter_with_client("FargateProfileCreated", waiter_model, eks_client)
    waiter.wait(fargateProfileName=profile_name, clusterName=cluster_name)
    _logger.debug(f"Created EKS Fargate Profile: {profile_name}")


def delete_fargate_profile(
    profile_name: str,
    cluster_name: str,
) -> None:
    _logger.debug(f"Deleting EKS Fargate Profile: {profile_name}")

    if describe_fargate_profile(profile_name=profile_name, cluster_name=cluster_name) is None:
        _logger.debug(f"EKS Fargate Profile not found: {profile_name}")
        return

    eks_client = boto3_client("eks")

    try:
        timeout = 0
        _logger.debug(f"Checking {cluster_name} cluster current state")
        res = eks_client.describe_cluster(name=cluster_name)
        eks_status = res.get("cluster").get("status")
        _logger.debug(f"{cluster_name} current state: {eks_status}")

        while eks_status != "ACTIVE" and timeout < 15:
            _logger.debug(f"EKS is an {eks_status} state. Retrying in 1min - attempt {timeout}")
            time.sleep(60)
            timeout += 1
            res = eks_client.describe_cluster(name=cluster_name)
            eks_status = res.get("cluster").get("status")

        timeout = 0
        _logger.debug(f"Checking fargate profile {profile_name} current state")
        fargate_profile_res = eks_client.describe_fargate_profile(
            clusterName=cluster_name, fargateProfileName=profile_name
        )
        fargate_profile_status = fargate_profile_res.get("fargateProfile").get("status")
        _logger.debug(f"{profile_name} current state: {fargate_profile_status}")

        while fargate_profile_status != "ACTIVE" and timeout < 15:
            _logger.debug(f"Fargate profile is in {fargate_profile_status} state. Retrying in 1min - attempt {timeout}")
            time.sleep(60)
            timeout += 1
            fargate_profile_res = eks_client.describe_fargate_profile(
                clusterName=cluster_name, fargateProfileName=profile_name
            )
            fargate_profile_status = fargate_profile_res.get("fargateProfile").get("status")

        _logger.debug(f"Deleting fargate profile {profile_name}")
        eks_client.delete_fargate_profile(
            fargateProfileName=profile_name,
            clusterName=cluster_name,
        )

    except eks_client.exceptions.ResourceNotFoundException as err:
        _logger.debug(err)

    waiter_model = WaiterModel(WAITER_CONFIG)
    waiter = create_waiter_with_client("FargateProfileDeleted", waiter_model, eks_client)
    waiter.wait(fargateProfileName=profile_name, clusterName=cluster_name)
    _logger.debug(f"Deleted EKS Fargate Profile: {profile_name}")
