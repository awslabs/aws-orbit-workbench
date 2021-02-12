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
from typing import Any, Dict, List, Union, cast

import boto3

_logger = logging.getLogger()

PROFILE_TYPE = Dict[str, Union[str, Dict[str, Any]]]
PROFILES_TYPE = List[PROFILE_TYPE]


class TeamConstants:
    def __init__(self) -> None:
        self.env_name = os.environ["AWS_ORBIT_ENV"]
        self.team_name = os.environ["AWS_ORBIT_TEAM_SPACE"]
        self.region = os.environ["AWS_DEFAULT_REGION"]
        self.account_id = str(boto3.client("sts").get_caller_identity().get("Account"))

    def volumes(self) -> List[Dict[str, Any]]:
        return [{"name": "efs-volume", "persistentVolumeClaim": {"claimName": "jupyterhub"}}]

    def default_image(self) -> str:
        return f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/orbit-{self.env_name}-{self.team_name}:latest"

    def default_spark_image(self) -> str:
        return (
            f"{self.account_id}.dkr.ecr.{self.region}.amazonaws.com/orbit-{self.env_name}-{self.team_name}-spark:latest"
        )

    def default_profiles(self) -> PROFILES_TYPE:
        return [
            {
                "display_name": "Nano",
                "slug": "nano",
                "description": "1 CPU + 1G MEM",
                "properties": {
                    "cpu_guarantee": 1,
                    "cpu_limit": 1,
                    "mem_guarantee": "1G",
                    "mem_limit": "1G",
                    "storage_capacity": "2Gi",
                },
            },
            {
                "display_name": "Micro",
                "slug": "micro",
                "description": "2 CPU + 2G MEM",
                "properties": {
                    "cpu_guarantee": 2,
                    "cpu_limit": 2,
                    "mem_guarantee": "2G",
                    "mem_limit": "2G",
                },
                "default": True,
            },
            {
                "display_name": "Small",
                "slug": "small",
                "description": "4 CPU + 8G MEM",
                "properties": {
                    "cpu_guarantee": 4,
                    "cpu_limit": 4,
                    "mem_guarantee": "8G",
                    "mem_limit": "8G",
                },
            },
            {
                "display_name": "Small (Apache Spark)",
                "slug": "small-spark",
                "description": "4 CPU + 8G MEM",
                "properties": {
                    "image": self.default_spark_image(),
                    "cpu_guarantee": 4,
                    "cpu_limit": 4,
                    "mem_guarantee": "8G",
                    "mem_limit": "8G",
                },
            },
        ]

    def team_profiles(self) -> PROFILES_TYPE:
        ssm = boto3.Session().client("ssm")
        ssm_parameter_name: str = f"/orbit/{self.env_name}/teams/{self.team_name}/manifest"
        json_str: str = ssm.get_parameter(Name=ssm_parameter_name)["Parameter"]["Value"]

        team_manifest_dic = cast(PROFILES_TYPE, json.loads(json_str))
        default_profiles: PROFILES_TYPE = []
        if team_manifest_dic.get("profiles"):
            default_profiles = team_manifest_dic["profiles"]
        if len(default_profiles) == 0:
            default_profiles = self.default_profiles()

        ssm_parameter_name: str = f"/orbit/{self.env_name}/teams/{self.team_name}/user/profiles"
        json_str: str = ssm.get_parameter(Name=ssm_parameter_name)["Parameter"]["Value"]

        user_profiles: PROFILES_TYPE = cast(PROFILES_TYPE, json.loads(json_str))
        default_profiles.extend(user_profiles)
        _logger.debug("profiles:%s", default_profiles)
        return default_profiles

    def default_profile(self) -> PROFILE_TYPE:
        for p in self.team_profiles():
            if "default" in p and (p["default"] == "True" or p["default"] == True):
                return p
        return None
