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

from typing import ClassVar, List, Type
from marshmallow_dataclass import dataclass
from marshmallow import Schema

from aws_orbit.models.common import BaseSchema
from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


@dataclass(base_schema=BaseSchema, frozen=True)
class UserIdGroupPair:
    description: str
    group_id: str


@dataclass(base_schema=BaseSchema, frozen=True)
class IpPermission:
    Schema: ClassVar[Type[Schema]] = Schema
    from_port: int
    to_port: int
    ip_protocol: str
    user_id_group_pairs: List[UserIdGroupPair]


def authorize_security_group_ingress(group_id: str, ip_permissions: List[IpPermission]) -> None:
    permissions = [IpPermission.Schema().dump(i) for i in ip_permissions]
    _logger.debug(f"Authorizing Ingress for Security Group: {group_id}\nPermissions: {permissions}")

    ec2_client = boto3_client("ec2")
    ec2_client.authorize_security_group_ingress(
        GroupId=group_id,
        IpPermissions=permissions
    )


def revoke_security_group_ingress(group_id: str, ip_permissions: List[IpPermission]) -> None:
