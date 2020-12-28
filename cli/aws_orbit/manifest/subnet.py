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
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

import botocore.exceptions

if TYPE_CHECKING:
    from aws_orbit.manifest import MANIFEST_TYPE, Manifest
    from aws_orbit.manifest.vpc import MANIFEST_VPC_TYPE

_logger: logging.Logger = logging.getLogger(__name__)


MANIFEST_SUBNET_TYPE = Dict[str, Optional[str]]


class SubnetKind(Enum):
    private: str = "private"
    public: str = "public"
    isolated: str = "isolated"


class SubnetManifest:
    def __init__(
        self,
        manifest: "Manifest",
        subnet_id: str,
        kind: SubnetKind,
    ) -> None:
        self.manifest: "Manifest" = manifest
        self.subnet_id = subnet_id
        self.kind = kind

        # Need to fill up

        self.cidr_block: Optional[str] = None  # Demo
        self.availability_zone: Optional[str] = None  # Demo
        self.route_table_id: Optional[str] = None  # Demo
        self.vpc_id: Optional[str] = None  # Demo

    def _fetch_route_table_id(self) -> None:
        ec2_client = self.manifest.boto3_client("ec2")
        res: Dict[str, Any] = ec2_client.describe_route_tables(
            Filters=[{"Name": "association.subnet-id", "Values": [self.subnet_id]}]
        )
        for route_table in res["RouteTables"]:
            if "Associations" in route_table:
                for association in route_table["Associations"]:
                    if association["SubnetId"] == self.subnet_id:
                        self.route_table_id = association["RouteTableId"]
                        return

    def fillup_from_ssm(self) -> None:
        if self.manifest.raw_ssm is not None:
            raw: "MANIFEST_TYPE" = self.manifest.raw_ssm
            if raw.get("vpc") is not None:
                raw_vpc = cast("MANIFEST_VPC_TYPE", raw.get("vpc"))
                for subnet in cast(List[MANIFEST_SUBNET_TYPE], raw_vpc.get("subnets", [])):
                    if subnet.get("subnet-id") == self.subnet_id:
                        self.vpc_id = subnet.get("vpc-id")
                        self.cidr_block = subnet.get("cidr-block")
                        self.availability_zone = subnet.get("availability-zone")
                        self.route_table_id = subnet.get("route-table-id")
                        _logger.debug("Subnet %s loaded successfully from SSM.", self.subnet_id)
                        return

    def fetch_properties(self) -> None:
        try:
            ec2 = self.manifest.boto3_resource("ec2")
            subnet = ec2.Subnet(self.subnet_id)
            self.cidr_block = str(subnet.cidr_block)
            self.availability_zone = str(subnet.availability_zone)
            self.vpc_id = str(subnet.vpc_id)
            self._fetch_route_table_id()
            _logger.debug("Subnet %s loaded successfully from resources.", self.subnet_id)
        except botocore.exceptions.ClientError:
            _logger.debug("Unable to fetch properties from subnet (%s) right now.", self.subnet_id)

    def asdict_file(self) -> str:
        return self.subnet_id

    def asdict(self) -> MANIFEST_SUBNET_TYPE:
        return {
            "subnet-id": self.subnet_id,
            "route-table-id": self.route_table_id,
            "vpc-id": self.vpc_id,
            "cidr-block": self.cidr_block,
            "availability-zone": self.availability_zone,
            "kind": self.kind.value,
        }
