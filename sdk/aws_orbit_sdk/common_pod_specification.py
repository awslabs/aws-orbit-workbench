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
from typing import Any, Dict, List, Optional, Union, cast

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

    def default_profiles(self) -> PROFILES_TYPE:
        return [
            {
                "display_name": "Nano",
                "slug": "nano",
                "description": "1 CPU + 1G MEM",
                "kubespawner_override": {"cpu_guarantee": 1, "cpu_limit": 1, "mem_guarantee": "1G", "mem_limit": "1G"},
            },
            {
                "display_name": "Micro",
                "slug": "micro",
                "description": "2 CPU + 2G MEM",
                "kubespawner_override": {
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
                "kubespawner_override": {
                    "cpu_guarantee": 4,
                    "cpu_limit": 4,
                    "mem_guarantee": "8G",
                    "mem_limit": "8G",
                },
            },
        ]

    def deployed_profiles(self) -> PROFILES_TYPE:
        ssm = boto3.Session().client("ssm")
        ssm_parameter_name: str = f"/orbit/{self.env_name}/teams/{self.team_name}/context"
        json_str: str = ssm.get_parameter(Name=ssm_parameter_name)["Parameter"]["Value"]

        team_manifest_dic = cast(PROFILES_TYPE, json.loads(json_str))
        deployed_profiles: PROFILES_TYPE = []
        if team_manifest_dic.get("profiles"):
            deployed_profiles = team_manifest_dic["profiles"]
        if len(deployed_profiles) == 0:
            deployed_profiles = self.default_profiles()

        return deployed_profiles

    def team_profiles(self) -> PROFILES_TYPE:
        ssm = boto3.Session().client("ssm")

        default_profiles = self.deployed_profiles()

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

    def profile(self, name: str) -> PROFILE_TYPE:
        for p in self.team_profiles():
            if p["slug"] == name:
                return p
        return None
