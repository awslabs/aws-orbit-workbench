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

from botocore.exceptions import WaiterError
from botocore.waiter import WaiterModel, create_waiter_with_client
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from datamaker_cli.manifest import Manifest

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
                {
                    "matcher": "path",
                    "expected": "ACTIVE",
                    "argument": "fargateProfile.status",
                    "state": "success"
                },
                {
                    "matcher": "path",
                    "expected": "CREATING",
                    "argument": "fargateProfile.status",
                    "state": "retry"
                },
                {
                    "matcher": "path",
                    "expected": "CREATE_FAILED",
                    "argument": "fargateProfile.status",
                    "state": "failure"
                },
            ]
        },
        "FargateProfileDeleted": {
            "operation": "DescribeFargateProfile",
            "delay": DELAY,
            "maxAttempts": MAX_ATTEMPTS,
            "acceptors": [
                {
                    "expected": "ResourceNotFoundException",
                    "matcher": "error",
                    "state": "success"
                },
                {
                    "matcher": "path",
                    "expected": "DELETING",
                    "argument": "fargateProfile.status",
                    "state": "retry"
                },
                {
                    "matcher": "path",
                    "expected": "DELETE_FAILED",
                    "argument": "fargateProfile.status",
                    "state": "failure"
                },
            ]
        },
    }
}


def create_fargate_profile(manifest: Manifest, profile_name: str, cluster_name: str, role_arn: str, subnets: List[str], namespace: str, selector_labels: Dict[str, str]) -> None:
    _logger.debug(f"Creating EKS Fargate Profile: {profile_name}")
    eks_client = manifest.boto3_client("eks")

    eks_client.create_fargate_profile(
        fargateProfileName=profile_name,
        clusterName=cluster_name,
        podExecutionRoleArn=role_arn,
        subnets=subnets,
        selectors=[
            {
                "namespace": namespace,
                "labels": selector_labels,
            },
        ]
    )

    waiter_model = WaiterModel(WAITER_CONFIG)
    waiter = create_waiter_with_client("FargateProfileCreated", waiter_model, eks_client)
    waiter.wait(
        fargateProfileName=profile_name,
        clusterName=cluster_name
    )
    _logger.debug(f"Created EKS Fargate Profile: {profile_name}")


def delete_fargate_profile(manifest: Manifest, profile_name: str, cluster_name: str,) -> None:
    _logger.debug(f"Deleting EKS Fargate Profile: {profile_name}")
    eks_client = manifest.boto3_client("eks")

    eks_client.delete_fargate_profile(
        fargateProfileName=profile_name,
        clusterName=cluster_name,
    )

    waiter_model = WaiterModel(WAITER_CONFIG)
    waiter = create_waiter_with_client("FargateProfileDeleted", waiter_model, eks_client)
    waiter.wait(
        fargateProfileName=profile_name,
        clusterName=cluster_name
    )
    _logger.debug(f"Deleted EKS Fargate Profile: {profile_name}")


