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
from typing import cast

from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def modify_vpc_endpoint(vpc_id: str, service_name: str, private_dns_enabled: bool) -> None:
    ec2_client = boto3_client("ec2")
    paginator = ec2_client.get_paginator("describe_vpc_endpoints")
    _logger.debug("Modifying VPC Endpoints for VPC: %s", vpc_id)
    response_iterator = paginator.paginate(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}], MaxResults=50)
    for response in response_iterator:
        for ep in response["VpcEndpoints"]:
            ep_s_name = ep["ServiceName"]
            _logger.debug(f"ep_s_name={ep_s_name}")
            if service_name in ep["ServiceName"]:
                ec2_client.modify_vpc_endpoint(VpcEndpointId=ep["VpcEndpointId"], PrivateDnsEnabled=private_dns_enabled)


def get_env_vpc_id(env_name: str) -> str:
    ec2_client = boto3_client("ec2")
    paginator = ec2_client.get_paginator("describe_vpcs")
    response_iterator = paginator.paginate(Filters=[{"Name": "tag:Env", "Values": [f"orbit-{env_name}"]}])
    for response in response_iterator:
        for vpc in response["Vpcs"]:
            return cast(str, vpc["VpcId"])
    raise ValueError(f"VPC not found for env {env_name}.")
