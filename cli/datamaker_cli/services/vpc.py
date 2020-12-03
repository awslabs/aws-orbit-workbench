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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datamaker_cli.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def modify_vpc_endpoint(manifest: "Manifest", service_name: str, private_dns_enabled: bool) -> None:
    if manifest.vpc.vpc_id is None:
        manifest.fetch_network_data()
    vpc_id = manifest.vpc.vpc_id
    ec2_client = manifest.boto3_client("ec2")
    paginator = ec2_client.get_paginator("describe_vpc_endpoints")
    response_iterator = paginator.paginate(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}], MaxResults=25)
    for response in response_iterator:
        for ep in response["VpcEndpoints"]:
            ep_s_name = ep["ServiceName"]
            _logger.debug(f"ep_s_name={ep_s_name}")
            if service_name in ep["ServiceName"]:
                ec2_client.modify_vpc_endpoint(VpcEndpointId=ep["VpcEndpointId"], PrivateDnsEnabled=private_dns_enabled)
