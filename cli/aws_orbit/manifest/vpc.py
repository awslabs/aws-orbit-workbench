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
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Union, cast

import botocore.exceptions
from aws_orbit.manifest.subnet import MANIFEST_SUBNET_TYPE, SubnetKind, SubnetManifest

if TYPE_CHECKING:
    from aws_orbit.manifest import MANIFEST_TYPE, Manifest

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST_FILE_VPC_TYPE = Dict[str, List[str]]
MANIFEST_VPC_TYPE = Dict[str, Union[None, str, List[str], List[MANIFEST_SUBNET_TYPE]]]


class VpcManifest:
    def __init__(
        self,
        manifest: "Manifest",
        subnets: List[SubnetManifest],
    ) -> None:
        self.manifest: "Manifest" = manifest
        self.subnets: List[SubnetManifest] = subnets

        # Need to fill up

        self.vpc_id: Optional[str] = None  # Demo
        self.cidr_block: Optional[str] = None  # Demo
        self.availability_zones: Optional[List[str]] = None  # Demo

    def _fetch_vpc_cidr(self) -> None:
        if self.vpc_id is not None:
            ec2 = self.manifest.boto3_resource("ec2")
            vpc = ec2.Vpc(self.vpc_id)
            self.cidr_block = str(vpc.cidr_block)

    def _fetch_vpc_id(self) -> None:
        vpc_ids: Set[str] = set(s.vpc_id for s in self.subnets if s.vpc_id is not None)
        _logger.debug("vpc_ids: %s", vpc_ids)
        if len(vpc_ids) == 1:
            self.vpc_id = vpc_ids.pop()

    def _fetch_subnets_properties(self) -> None:
        for subnet in self.subnets:
            subnet.fetch_properties()

    def fillup_from_ssm(self) -> None:
        if self.manifest.raw_ssm is not None:
            raw: "MANIFEST_TYPE" = self.manifest.raw_ssm
            if raw.get("vpc") is not None:
                raw_vpc = cast("MANIFEST_VPC_TYPE", raw.get("vpc"))
                self.vpc_id = cast(Optional[str], raw_vpc.get("vpc-id"))
                self.cidr_block = cast(Optional[str], raw_vpc.get("cidr-block"))
                self.availability_zones = cast(Optional[List[str]], raw_vpc.get("availability-zones"))
                for subnet in self.subnets:
                    subnet.fillup_from_ssm()
                _logger.debug("Vpc %s loaded successfully from SSM.", self.vpc_id)

    def fetch_properties(self) -> None:
        try:
            self._fetch_subnets_properties()
            self._fetch_vpc_id()
            self._fetch_vpc_cidr()
            azs = sorted(list(set(s.availability_zone for s in self.subnets if s.availability_zone is not None)))
            if azs:
                self.availability_zones = azs
            else:
                self.availability_zones = None
        except botocore.exceptions.ClientError:
            _logger.debug("Unable to fetch properties from VPC right now.")

    def asdict_file(self) -> MANIFEST_FILE_VPC_TYPE:
        return {
            "private-subnets-ids": [s.subnet_id for s in self.subnets if s.kind is SubnetKind.private],
            "public-subnets-ids": [s.subnet_id for s in self.subnets if s.kind is SubnetKind.public],
            "isolated-subnets-ids": [s.subnet_id for s in self.subnets if s.kind is SubnetKind.isolated],
        }

    def asdict(self) -> MANIFEST_VPC_TYPE:
        return {
            "vpc-id": self.vpc_id,
            "cidr-block": self.cidr_block,
            "availability-zones": self.availability_zones,
            "subnets": [s.asdict() for s in self.subnets],
        }


def parse_vpc(manifest: "Manifest") -> VpcManifest:
    subnets: List[SubnetManifest] = []

    if manifest.internet_accessible:
        for s in manifest.nodes_subnets:
            _logger.debug("Adding private subnet %s in the manifest.", s)
            subnets.append(SubnetManifest(manifest=manifest, subnet_id=s, kind=SubnetKind.private))
    else:
        for s in manifest.nodes_subnets:
            _logger.debug("Adding isolated subnet %s in the manifest.", s)
            subnets.append(SubnetManifest(manifest=manifest, subnet_id=s, kind=SubnetKind.isolated))

    for s in manifest.load_balancers_subnets:
        _logger.debug("Adding public subnet %s in the manifest.", s)
        subnets.append(SubnetManifest(manifest=manifest, subnet_id=s, kind=SubnetKind.public))

    return VpcManifest(
        manifest=manifest,
        subnets=subnets,
    )
