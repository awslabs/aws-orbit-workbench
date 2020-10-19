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

import json
import logging
import os
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, cast

import boto3
import yaml
from botocore.exceptions import ClientError

from datamaker_cli.exceptions import VpcNotFound
from datamaker_cli.utils import get_account_id, replace_dashes, replace_underscores

_logger: logging.Logger = logging.getLogger(__name__)


class SubnetKind(Enum):
    private = "private"
    public = "public"
    isolated = "isolated"


class SubnetManifest:
    def __init__(
        self,
        subnet_id: str,
        kind: SubnetKind,
        cidr_block: Optional[str] = None,
        availability_zone: Optional[str] = None,
        route_table_id: Optional[str] = None,
        vpc_id: Optional[str] = None,
    ) -> None:
        self.subnet_id = subnet_id
        self.cidr_block = cidr_block
        self.availability_zone = availability_zone
        self.route_table_id = route_table_id
        self.kind = kind
        self.vpc_id = vpc_id

    def _fetch_route_table_id(self) -> None:
        ec2_client = boto3.client("ec2")
        res: Dict[str, Any] = ec2_client.describe_route_tables(
            Filters=[{"Name": "association.subnet-id", "Values": [self.subnet_id]}]
        )
        for route_table in res["RouteTables"]:
            if "Associations" in route_table:
                for association in route_table["Associations"]:
                    if association["SubnetId"] == self.subnet_id:
                        self.route_table_id = association["RouteTableId"]
                        return

    def fetch_properties(self) -> None:
        ec2 = boto3.resource("ec2")
        subnet = ec2.Subnet(self.subnet_id)
        self.cidr_block = str(subnet.cidr_block)
        self.availability_zone = str(subnet.availability_zone)
        self.vpc_id = str(subnet.vpc_id)
        self._fetch_route_table_id()

    def repr_full(self) -> Dict[str, str]:
        repr: Dict[str, str] = replace_underscores(vars(self))
        repr["kind"] = self.kind.value
        return repr


VPC_REPR_MINIMAL_TYPE = Dict[str, List[str]]
VPC_REPR_FULL_TYPE = Dict[str, Union[str, List[Dict[str, str]]]]


class VpcManifest:
    def __init__(
        self,
        subnets: List[SubnetManifest],
        vpc_id: Optional[str] = None,
        cidr_block: Optional[str] = None,
        availability_zones: Optional[List[str]] = None,
    ) -> None:
        self.vpc_id = vpc_id
        self.cidr_block = cidr_block
        self.subnets: List[SubnetManifest] = subnets
        self.availability_zones: Optional[List[str]] = availability_zones

    def repr_minimal(self) -> VPC_REPR_MINIMAL_TYPE:
        return {
            "private-subnets-ids": [s.subnet_id for s in self.subnets if s.kind is SubnetKind.private],
            "public-subnets-ids": [s.subnet_id for s in self.subnets if s.kind is SubnetKind.public],
            "isolated-subnets-ids": [s.subnet_id for s in self.subnets if s.kind is SubnetKind.isolated],
        }

    def repr_full(self) -> VPC_REPR_FULL_TYPE:
        repr: VPC_REPR_FULL_TYPE = replace_underscores(vars(self))
        repr["subnets"] = [s.repr_full() for s in self.subnets]
        return repr

    def _fetch_vpc_id(self) -> None:
        vpc_ids: Set[str] = set(s.vpc_id for s in self.subnets if s.vpc_id is not None)
        if not vpc_ids:
            self._fetch_subnets_properties()
            vpc_ids = set(s.vpc_id for s in self.subnets if s.vpc_id is not None)
        _logger.debug("vpc_ids: %s", vpc_ids)
        if len(vpc_ids) != 1:
            raise VpcNotFound(
                "All your subnet IDs MUST belong to the same VPC. "
                f"Currently you have these VPC IDS referenced: {vpc_ids} "
            )
        self.vpc_id = vpc_ids.pop()

    def _fetch_vpc_cidr(self) -> None:
        ec2 = boto3.resource("ec2")
        if self.vpc_id is None:
            self._fetch_vpc_id()
        vpc = ec2.Vpc(self.vpc_id)
        self.cidr_block = str(vpc.cidr_block)

    def _fetch_subnets_properties(self) -> None:
        for subnet in self.subnets:
            try:
                subnet.fetch_properties()
            except ClientError:
                _logger.warning("Unable to fetch properties from subnet (%s)", subnet.subnet_id)

    def fetch_vpc_properties(self) -> None:
        self._fetch_subnets_properties()
        self._fetch_vpc_id()
        self._fetch_vpc_cidr()
        self.availability_zones = sorted(
            list(set(s.availability_zone for s in self.subnets if s.availability_zone is not None))
        )


TEAM_REPR_MINIMAL_TYPE = Dict[str, Union[str, int]]
TEAM_REPR_FULL_TYPE = Dict[str, Union[str, int, None]]


class TeamManifest:
    def __init__(
        self,
        name: str,
        env_name: str,
        instance_type: str,
        local_storage_size: int,
        nodes_num_desired: int,
        nodes_num_max: int,
        nodes_num_min: int,
        policy: str,
        efs_id: Optional[str] = None,
        eks_nodegroup_role_arn: Optional[str] = None,
        jupyterhub_url: Optional[str] = None,
    ) -> None:
        self.name = name
        self.env_name = env_name
        self.instance_type = instance_type
        self.local_storage_size = local_storage_size
        self.nodes_num_desired = nodes_num_desired
        self.nodes_num_max = nodes_num_max
        self.nodes_num_min = nodes_num_min
        self.policy = policy
        self.efs_id = efs_id
        self.eks_nodegroup_role_arn = eks_nodegroup_role_arn
        self.jupyterhub_url = jupyterhub_url
        self.ssm_parameter_name = f"/datamaker/{self.env_name}/teams/{self.name}/manifest"

    def read_ssm(self) -> None:
        client = boto3.client(service_name="ssm")
        try:
            json_str: str = client.get_parameter(Name=f"/datamaker/{self.env_name}/teams/{self.name}/manifest")[
                "Parameter"
            ]["Value"]
        except client.exceptions.ParameterNotFound:
            _logger.debug(f"Team {self.name} manifest does not exist yet.")
        else:
            _logger.debug(f"Reading team {self.name} manifest from it's own SSM")
            raw = cast(Dict[str, Any], json.loads(json_str))
            for k, v in replace_dashes(raw).items():
                setattr(self, k, v)

    def repr_minimal(self) -> TEAM_REPR_MINIMAL_TYPE:
        return {
            "name": self.name,
            "instance-type": self.instance_type,
            "local-storage-size": self.local_storage_size,
            "nodes-num-desired": self.nodes_num_desired,
            "nodes-num-max": self.nodes_num_max,
            "nodes-num-min": self.nodes_num_min,
            "policy": self.policy,
        }

    def repr_full(self) -> TEAM_REPR_FULL_TYPE:
        return replace_underscores(vars(self))

    def repr_full_as_string(self) -> str:
        return str(json.dumps(obj=self.repr_full(), indent=4, sort_keys=False))

    def write_ssm(self) -> None:
        client = boto3.client(service_name="ssm")
        client.put_parameter(Name=self.ssm_parameter_name, Value=self.repr_full_as_string(), Overwrite=True)


PLUGIN_REPR_MINIMAL_TYPE = Dict[str, str]
PLUGIN_REPR_FULL_TYPE = Dict[str, str]


class PluginManifest:
    def __init__(
        self,
        name: str,
    ) -> None:
        self.name = name

    def repr_minimal(self) -> PLUGIN_REPR_MINIMAL_TYPE:
        return self.repr_full()

    def repr_full(self) -> PLUGIN_REPR_FULL_TYPE:
        return replace_underscores(vars(self))


MANIFEST_REPR_MINIMAL_TYPE = Dict[
    str, Union[str, bool, VPC_REPR_MINIMAL_TYPE, List[TEAM_REPR_MINIMAL_TYPE], List[PLUGIN_REPR_MINIMAL_TYPE]]
]
MANIFEST_REPR_FULL_TYPE = Dict[
    str, Union[str, bool, VPC_REPR_FULL_TYPE, List[TEAM_REPR_MINIMAL_TYPE], List[PLUGIN_REPR_MINIMAL_TYPE]]
]


class Manifest:
    def __init__(
        self,
        name: str,
        region: str,
        demo: bool,
        dev: bool,
        vpc: VpcManifest,
        teams: List[TeamManifest],
        plugins: List[PluginManifest],
        account_id: Optional[str] = None,
        available_eks_regions: Optional[List[str]] = None,
        eks_cluster_role_arn: Optional[str] = None,
        eks_env_nodegroup_role_arn: Optional[str] = None,
        user_pool_id: Optional[str] = None,
        user_pool_client_id: Optional[str] = None,
        identity_pool_id: Optional[str] = None,
    ) -> None:
        self.name = name
        self.region = region
        self.demo = demo
        self.dev = dev
        self.vpc = vpc
        self.teams = teams
        self.plugins = plugins
        self._account_id = account_id
        self.available_eks_regions = available_eks_regions
        self.eks_cluster_role_arn = eks_cluster_role_arn
        self.eks_env_nodegroup_role_arn = eks_env_nodegroup_role_arn
        self.user_pool_id = user_pool_id
        self.user_pool_client_id = user_pool_client_id
        self.identity_pool_id = identity_pool_id
        self.ssm_parameter_name = f"/datamaker/{self.name}/manifest"
        boto3.setup_default_session(region_name=self.region)
        self.toolkit_s3_bucket = f"datamaker-{self.name}-toolkit-{self.account_id}"
        self.toolkit_codebuild_project = f"datamaker-{self.name}"

    @property
    def account_id(self) -> str:
        if self._account_id is None:
            self._account_id = get_account_id()
        return self._account_id

    def read_ssm(self) -> None:
        client = boto3.client(service_name="ssm")
        try:
            json_str: str = client.get_parameter(Name=f"/datamaker/{self.name}/manifest")["Parameter"]["Value"]
        except client.exceptions.ParameterNotFound:
            self.available_eks_regions = boto3.Session().get_available_regions("eks")
            self.vpc.fetch_vpc_properties()
        else:
            raw = cast(Dict[str, Any], json.loads(json_str))
            subnets_args = [replace_dashes(s) for s in raw["vpc"]["subnets"]]
            for s in subnets_args:
                s["kind"] = SubnetKind(value=s["kind"])
            subnets = [SubnetManifest(**s) for s in subnets_args]
            self.vpc = VpcManifest(
                subnets=subnets, **{k.replace("-", "_"): v for k, v in raw["vpc"].items() if k != "subnets"}
            )
            self.teams = [TeamManifest(env_name=self.name, **replace_dashes(team)) for team in raw["teams"]]
            for team in self.teams:
                team.read_ssm()
            self.plugins = [PluginManifest(**replace_dashes(plugin)) for plugin in raw["plugins"]]
            for k, v in replace_dashes(raw).items():
                if k not in ("vpc", "teams", "plugins"):
                    setattr(self, k, v)

    def repr_minimal(self) -> MANIFEST_REPR_MINIMAL_TYPE:
        repr: MANIFEST_REPR_MINIMAL_TYPE = {
            "name": self.name,
            "region": self.region,
            "vpc": self.vpc.repr_minimal(),
            "teams": [t.repr_minimal() for t in self.teams],
            "plugins": [p.repr_minimal() for p in self.plugins],
        }
        if self.demo:
            repr["demo"] = True
        if self.dev:
            repr["dev"] = True
        return repr

    def repr_full(self) -> MANIFEST_REPR_FULL_TYPE:
        repr: MANIFEST_REPR_FULL_TYPE = replace_underscores(vars(self))
        repr["vpc"] = self.vpc.repr_full()
        repr["teams"] = [t.repr_minimal() for t in self.teams]
        repr["plugins"] = [p.repr_full() for p in self.plugins]
        return repr

    def repr_full_as_string(self) -> str:
        return str(json.dumps(obj=self.repr_full(), indent=4, sort_keys=False))

    def write_ssm(self) -> None:
        client = boto3.client(service_name="ssm")
        client.put_parameter(Name=self.ssm_parameter_name, Value=self.repr_full_as_string(), Overwrite=True)

    def write_file(self, filename: str) -> None:
        _logger.debug("filename: %s", filename)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as file:
            yaml.safe_dump(data=self.repr_minimal(), stream=file, sort_keys=False, indent=4)


def read_manifest_file(filename: str) -> Manifest:
    _logger.debug("filename: %s", filename)
    with open(filename, "r") as f:
        raw: Any = yaml.safe_load(f)
        if isinstance(raw, dict) is False:
            raise TypeError("Invalid datamaker.yaml structure, it MUST reflect a dictionary.")
        raw = cast(Dict[str, Any], raw)
        subnets = [SubnetManifest(subnet_id=i, kind=SubnetKind.private) for i in raw["vpc"]["private-subnets-ids"]]
        subnets += [SubnetManifest(subnet_id=i, kind=SubnetKind.public) for i in raw["vpc"]["public-subnets-ids"]]
        return Manifest(
            name=raw["name"],
            region=raw["region"],
            vpc=VpcManifest(subnets=subnets),
            teams=[TeamManifest(env_name=raw["name"], **replace_dashes(team)) for team in raw["teams"]],
            plugins=[PluginManifest(**replace_dashes(plugin)) for plugin in raw["plugins"]],
            demo=raw.get("demo", False),
            dev=raw.get("dev", False),
        )
