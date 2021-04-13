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

from aws_orbit_sdk import controller
from aws_orbit_sdk.common import get_workspace
from jupyter_server.base.handlers import APIHandler
from tornado import web

DATA: Dict[str, List[Dict[str, str]]] = {}


class EksRouteHandler(APIHandler):
    @staticmethod
    def _dump(data) -> str:
        ret: Dict[str, Any] = {}
        for ng in data:
            ngn = ng["nodegroup_name"]
            ret[ngn] = {}
            for ngk in ng.keys():
                ret[ngn][ngk] = ng[ngk]

        ret_resp = {"nodegroups": ret}
        return json.dumps(ret_resp)

    @web.authenticated
    def get(self):
        global DATA
        self.log.info(f"GET - {self.__class__}")
        if "MOCK" not in os.environ or os.environ["MOCK"] == "0":
            DATA = get_workspace()
            cluster_name = "orbit-" + DATA["env_name"]
            eks_nodegroups = controller.get_nodegroups(cluster_name=cluster_name)
            self.log.debug(f"eks_nodegroups={eks_nodegroups}")
            if "MOCK" in os.environ:
                path = f"{Path(__file__).parent.parent.parent}/test/mockup/compute-eks.json"
                self.log.info(f"writing mockup data to {path}")
                with open(path, "w") as outfile:
                    json.dump(eks_nodegroups, outfile, indent=4)
        else:
            path = f"{Path(__file__).parent.parent.parent}/test/mockup/compute-eks.json"
            with open(path) as f:
                eks_nodegroups = json.load(f)

        self.finish(self._dump(eks_nodegroups))
