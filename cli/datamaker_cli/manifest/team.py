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
from typing import TYPE_CHECKING, Dict, List, Optional, Union, cast

from datamaker_cli import utils
from datamaker_cli.manifest.plugin import MANIFEST_FILE_PLUGIN_TYPE, MANIFEST_PLUGIN_TYPE, PluginManifest

if TYPE_CHECKING:
    from datamaker_cli.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


MANIFEST_FILE_TEAM_TYPE = Dict[str, Union[str, int, None, List[MANIFEST_FILE_PLUGIN_TYPE]]]
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
        policy: str,
        plugins: List[PluginManifest],
        grant_sudo: bool,
        image: Optional[str] = None,
    ) -> None:
        self.manifest: "Manifest" = manifest
        self.name: str = name
        self.instance_type: str = instance_type
        self.local_storage_size: int = local_storage_size
        self.nodes_num_desired: int = nodes_num_desired
        self.nodes_num_max: int = nodes_num_max
        self.nodes_num_min: int = nodes_num_min
        self.policy: str = policy
        self.grant_sudo: bool = grant_sudo
        self.plugins: List[PluginManifest] = plugins
        self.image: Optional[str] = image
        if self.image is None:
            self.base_image_address: str = (
                f"{self.manifest.account_id}.dkr.ecr.{self.manifest.region}.amazonaws.com/"
                f"datamaker-{self.manifest.name}-jupyter-user"
            )
        else:
            self.base_image_address = (
                f"{self.manifest.account_id}.dkr.ecr.{self.manifest.region}.amazonaws.com/"
                f"datamaker-{self.manifest.name}-{self.image}"
            )
        self.final_image_address: str = (
            f"{self.manifest.account_id}.dkr.ecr.{self.manifest.region}.amazonaws.com/"
            f"datamaker-{self.manifest.name}-{self.name}"
        )
        self.stack_name: str = f"datamaker-{self.manifest.name}-{self.name}"
        self.ssm_parameter_name: str = f"/datamaker/{self.manifest.name}/teams/{self.name}/manifest"
        self.bootstrap_s3_prefix: str = f"teams/{self.name}/bootstrap/"
        self.scratch_bucket: Optional[str] = None
        self.scratch_retention_days: int = 30

        # Need to fill up
        self.raw_ssm: Optional[MANIFEST_TEAM_TYPE] = None
        self.efs_id: Optional[str] = None
        self.eks_nodegroup_role_arn: Optional[str] = None
        self.jupyter_url: Optional[str] = None
        self.ecs_cluster_name: Optional[str] = None
        self.ecs_task_definition_arn: Optional[str] = None
        self.ecs_container_runner_arn: Optional[str] = None

    def _read_manifest_ssm(self) -> Optional[MANIFEST_TEAM_TYPE]:
        _logger.debug("Trying to read manifest from SSM parameter.")
        client = self.manifest.boto3_client(service_name="ssm")
        try:
            json_str: str = client.get_parameter(Name=self.ssm_parameter_name)["Parameter"]["Value"]
        except client.exceptions.ParameterNotFound:
            _logger.debug("Team %s Manifest SSM parameter not found: %s", self.name, self.ssm_parameter_name)
            return None
        _logger.debug("Team %s Manifest SSM parameter found.", self.name)
        return cast(MANIFEST_TEAM_TYPE, json.loads(json_str))

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
            client.put_parameter(
                Name=self.ssm_parameter_name,
                Value=self.asjson(),
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
            "policy": self.policy,
            "grant-sudo": self.grant_sudo,
            "image": self.image,
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
        self.raw_ssm = self._read_manifest_ssm()
        if self.raw_ssm is not None:
            raw: MANIFEST_TEAM_TYPE = self.raw_ssm
            self.efs_id = cast(Optional[str], raw.get("efs-id"))
            self.eks_nodegroup_role_arn = cast(Optional[str], raw.get("eks-nodegroup-role-arn"))
            self.jupyter_url = cast(Optional[str], raw.get("jupyter-url"))
            self.scratch_bucket = cast(str, raw.get("scratch-bucket"))
            self.scratch_retention_days = cast(int, raw.get("scratch-retention-days"))
            self.ecs_cluster_name = cast(str, raw.get("ecs-cluster-name"))
            self.ecs_task_definition_arn = cast(str, raw.get("ecs-task-definition-arn"))
            self.ecs_container_runner_arn = cast(str, raw.get("ecs-container-runner-arn"))
            _logger.debug("Team %s loaded successfully from SSM.", self.name)

    def construct_ecr_repository_name(self, env: str) -> str:
        image = self.image if self.image is not None else "jupyter-user:latest"
        if ":" not in image:
            image += ":latest"
        return f"datamaker-{env}-{image}"

    def get_plugin_by_name(self, name: str) -> Optional[PluginManifest]:
        for p in self.plugins:
            if p.name == name:
                return p
        return None
