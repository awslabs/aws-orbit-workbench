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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, cast

from aws_orbit import utils
from aws_orbit.manifest.plugin import MANIFEST_PLUGIN_TYPE, PluginManifest, parse_plugins

if TYPE_CHECKING:
    from aws_orbit.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST_PROPERTY_MAP_TYPE = Dict[str, Union[str, Dict[str, Any]]]
MANIFEST_FILE_TEAM_TYPE = Dict[str, Union[str, int, None, List[MANIFEST_PROPERTY_MAP_TYPE], List[str]]]
MANIFEST_TEAM_TYPE = Dict[str, Union[str, int, None, List[MANIFEST_PLUGIN_TYPE]]]


class TeamManifest:
    def __init__(
        self,
        manifest: "Manifest",
        name: str,
        instance_type: str,
        local_storage_size: int,
        nodes_num_desired: int,
        nodes_num_max: int,
        nodes_num_min: int,
        policies: List[str],
        efs_life_cycle: str,
        plugins: List[PluginManifest],
        grant_sudo: bool,
        jupyterhub_inbound_ranges: List[str],
        image: Optional[str] = None,
        profiles: Optional[List[MANIFEST_PROPERTY_MAP_TYPE]] = None,
        elbs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        profiles = [] if profiles is None else profiles
        elbs = {} if elbs is None else elbs
        self.manifest: "Manifest" = manifest
        self.name: str = name
        self.instance_type: str = instance_type
        self.local_storage_size: int = local_storage_size
        self.nodes_num_desired: int = nodes_num_desired
        self.nodes_num_max: int = nodes_num_max
        self.nodes_num_min: int = nodes_num_min
        self.policies: List[str] = policies
        self.grant_sudo: bool = grant_sudo
        self.jupyterhub_inbound_ranges: List[str] = jupyterhub_inbound_ranges
        self.plugins: List[PluginManifest] = plugins
        self.image: Optional[str] = image
        self.profiles: List[MANIFEST_PROPERTY_MAP_TYPE] = profiles
        if self.image is None:
            self.base_image_address: str = (
                f"{self.manifest.account_id}.dkr.ecr.{self.manifest.region}.amazonaws.com/"
                f"orbit-{self.manifest.name}-jupyter-user"
            )
        else:
            self.base_image_address = (
                f"{self.manifest.account_id}.dkr.ecr.{self.manifest.region}.amazonaws.com/"
                f"orbit-{self.manifest.name}-{self.image}"
            )
        self.final_image_address: str = (
            f"{self.manifest.account_id}.dkr.ecr.{self.manifest.region}.amazonaws.com/"
            f"orbit-{self.manifest.name}-{self.name}"
        )
        self.stack_name: str = f"orbit-{self.manifest.name}-{self.name}"
        self.ssm_parameter_name: str = f"/orbit/{self.manifest.name}/teams/{self.name}/manifest"
        self.bootstrap_s3_prefix: str = f"teams/{self.name}/bootstrap/"
        self.scratch_bucket: Optional[str] = None
        self.scratch_retention_days: int = 30
        self.container_defaults = {"cpu": 4, "memory": 16384}
        self.efs_life_cycle = efs_life_cycle
        # Need to fill up
        self.raw_ssm: Optional[MANIFEST_TEAM_TYPE] = None
        self.efs_id: Optional[str] = None
        self.eks_nodegroup_role_arn: Optional[str] = None
        self.jupyter_url: Optional[str] = None
        self.ecs_cluster_name: Optional[str] = None
        self.container_runner_arn: Optional[str] = None
        self.eks_k8s_api_arn: Optional[str] = None
        self.elbs: Optional[Dict[str, Dict[str, Any]]] = elbs

    def write_manifest_ssm(self) -> None:
        client = self.manifest.boto3_client("ssm")
        _logger.debug("Writing team %s manifest to SSM parameter.", self.name)
        try:
            client.get_parameter(Name=self.ssm_parameter_name)["Parameter"]["Value"]
            exists: bool = True
        except client.exceptions.ParameterNotFound:
            exists = False
        _logger.debug("Does Team %s Manifest SSM parameter exist? %s", self.name, exists)
        if exists:
            json_str = self.asjson()
            # resolve any parameters inside team manifest per context
            json_str = utils.resolve_parameters(
                json_str, dict(region=self.manifest.region, account=self.manifest.account_id, env=self.manifest.name)
            )
            client.put_parameter(
                Name=self.ssm_parameter_name,
                Value=json_str,
                Overwrite=True,
                Tier="Intelligent-Tiering",
            )

    def asdict_file(self) -> MANIFEST_FILE_TEAM_TYPE:
        return {
            "name": self.name,
            "instance-type": self.instance_type,
            "local-storage-size": self.local_storage_size,
            "nodes-num-desired": self.nodes_num_desired,
            "nodes-num-max": self.nodes_num_max,
            "nodes-num-min": self.nodes_num_min,
            "policies": self.policies,
            "grant-sudo": self.grant_sudo,
            "image": self.image,
            "jupyterhub-inbound-ranges": self.jupyterhub_inbound_ranges,
            "profiles": self.profiles,
            "efs-life-cycle": self.efs_life_cycle,
            "plugins": [p.asdict_file() for p in self.plugins],
        }

    def asdict(self) -> MANIFEST_FILE_TEAM_TYPE:
        obj: MANIFEST_FILE_TEAM_TYPE = utils.replace_underscores(vars(self))
        obj["plugins"] = [p.asdict() for p in self.plugins]
        del obj["manifest"]
        del obj["raw-ssm"]
        return obj

    def asjson(self) -> str:
        return str(json.dumps(obj=self.asdict(), sort_keys=True))

    def fetch_ssm(self) -> None:
        _logger.debug("Fetching SSM manifest data (Team %s)...", self.name)
        self.raw_ssm = read_raw_manifest_ssm(manifest=self.manifest, team_name=self.name)
        if self.raw_ssm is not None:
            raw: MANIFEST_TEAM_TYPE = self.raw_ssm
            self.efs_id = cast(Optional[str], raw.get("efs-id"))
            self.eks_nodegroup_role_arn = cast(Optional[str], raw.get("eks-nodegroup-role-arn"))
            self.jupyter_url = cast(Optional[str], raw.get("jupyter-url"))
            self.scratch_bucket = cast(str, raw.get("scratch-bucket"))
            self.scratch_retention_days = cast(int, raw.get("scratch-retention-days"))
            self.ecs_cluster_name = cast(str, raw.get("ecs-cluster-name"))
            self.container_runner_arn = cast(str, raw.get("container-runner-arn"))
            self.eks_k8s_api_arn = cast(str, raw.get("eks-k8s-api-arn"))
            _logger.debug("Team %s loaded successfully from SSM.", self.name)

    def construct_ecr_repository_name(self, env: str) -> str:
        image = self.image if self.image is not None else "jupyter-user:latest"
        if ":" not in image:
            image += ":latest"
        return f"orbit-{env}-{image}"

    def get_plugin_by_id(self, plugin_id: str) -> Optional[PluginManifest]:
        for p in self.plugins:
            if p.plugin_id == plugin_id:
                return p
        return None


def parse_teams(manifest: "Manifest", raw_teams: List[MANIFEST_FILE_TEAM_TYPE]) -> List[TeamManifest]:
    return [
        TeamManifest(
            manifest=manifest,
            name=cast(str, t["name"]),
            instance_type=cast(str, t["instance-type"]),
            local_storage_size=cast(int, t["local-storage-size"]),
            nodes_num_desired=cast(int, t["nodes-num-desired"]),
            nodes_num_max=cast(int, t["nodes-num-max"]),
            nodes_num_min=cast(int, t["nodes-num-min"]),
            efs_life_cycle=cast(str, t["efs-life-cycle"]) if "efs-life-cycle" in t else "",
            policies=cast(List[str], t.get("policies", [])),
            grant_sudo=cast(bool, t.get("grant-sudo", False)),
            jupyterhub_inbound_ranges=cast(List[str], t.get("jupyterhub-inbound-ranges", [])),
            image=cast(Optional[str], t.get("image")),
            plugins=parse_plugins(team=t),
            profiles=cast(List[MANIFEST_PROPERTY_MAP_TYPE], t.get("profiles")),
        )
        for t in raw_teams
    ]


def read_raw_manifest_ssm(manifest: "Manifest", team_name: str) -> Optional[MANIFEST_TEAM_TYPE]:
    parameter_name: str = f"/orbit/{manifest.name}/teams/{team_name}/manifest"
    _logger.debug("Trying to read manifest from SSM parameter (%s).", parameter_name)
    client = manifest.boto3_client(service_name="ssm")
    try:
        json_str: str = client.get_parameter(Name=parameter_name)["Parameter"]["Value"]
    except client.exceptions.ParameterNotFound:
        _logger.debug("Team %s Manifest SSM parameter not found: %s", team_name, parameter_name)
        return None
    _logger.debug("Team %s Manifest SSM parameter found.", team_name)
    return cast(MANIFEST_TEAM_TYPE, json.loads(json_str))
