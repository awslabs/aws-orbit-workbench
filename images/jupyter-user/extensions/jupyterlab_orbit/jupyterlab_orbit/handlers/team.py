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
import os
from pathlib import Path
from typing import Any, Dict, List

from aws_orbit_sdk.common import get_workspace
from aws_orbit_sdk.common_pod_specification import TeamConstants
from jupyter_server.base.handlers import APIHandler
from tornado import web

DATA: Dict[str, List[Dict[str, str]]] = {}
PROFILES_DATA: List[Dict[str, str]] = {}


class TeamRouteHandler(APIHandler):
    @staticmethod
    def _dump(data, profiles_data) -> str:
        ret: Dict[str, Any] = {}
        common_props = ["Fargate", "ScratchBucket"]
        security_props = [
            "EksPodRoleArn",
            "TeamKmsKeyArn",
            "TeamSecurityGroupId",
            "GrantSudo",
            "K8Admin",
        ]
        ret["common"] = [
            {"name": "Environment Name", "value": data["env_name"]},
            {"name": "Team Name", "value": data["team_space"]},
            {"name": "EKS Cluster Name", "value": "orbit-" + data["env_name"]},
            {
                "name": "Current Image",
                "value": os.environ["AWS_ORBIT_IMAGE"].split("/")[-1],
            },
        ]
        for key, value in data.items():
            if key in common_props:
                ret["common"].append({"name": key, "value": str(value)})

        ret["security"] = {}
        for key, value in data.items():
            if key in security_props:
                ret["security"][key] = value

        ret["profiles"] = {}
        if profiles_data:
            for p in profiles_data:
                ret["profiles"][p["slug"]] = p

        ret["other"] = {}
        for key, value in data.items():
            if (
                key not in security_props
                and key not in common_props
                and key
                not in [
                    "Profiles",
                    "StackName",
                    "SsmParameterName",
                    "JupyterhubInboundRanges",
                ]
                and value
            ):
                ret["other"][key] = value

        return json.dumps(ret)

    @web.authenticated
    def get(self):
        global DATA
        self.log.info(f"GET - {self.__class__}")
        if "MOCK" not in os.environ or os.environ["MOCK"] == "0":
            DATA = get_workspace()
            PROFILES_DATA = TeamConstants().team_profiles()
            # hide some details
            if "Elbs" in DATA:
                del DATA["Elbs"]
            if "Plugins" in DATA:
                del DATA["Plugins"]

            if "MOCK" in os.environ:
                path = f"{Path(__file__).parent.parent.parent}/test/mockup/team.json"
                self.log.info(f"writing mockup data to {path}")
                with open(path, "w") as outfile:
                    json.dump(DATA, outfile, indent=4)
        else:
            path = f"{Path(__file__).parent.parent.parent}/test/mockup/team.json"
            with open(path) as f:
                DATA = json.load(f)

        self.finish(self._dump(DATA, PROFILES_DATA))
