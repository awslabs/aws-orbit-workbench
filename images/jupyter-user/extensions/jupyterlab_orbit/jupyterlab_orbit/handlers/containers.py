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
from typing import Dict, List

from aws_orbit_sdk import controller
from jupyter_server.base.handlers import APIHandler
from tornado import web

DATA: List[Dict[str, str]] = []


class ContainersRouteHandler(APIHandler):
    def _dump(self) -> str:
        data: List[Dict[str, str]] = []
        for c in DATA:
            container: Dict[str, str] = dict()
            container["name"] = c["metadata"]["name"]
            container["start_time"] = c["metadata"]["creationTimestamp"]
            if "labels" in c["metadata"] and "orbit/node-type" in c["metadata"]["labels"]:
                container["node_type"] = c["metadata"]["labels"]["orbit/node-type"]
            else:
                container["node_type"] = "unknown"

            # c['notebooks'] = ''
            data.append(container)
        return json.dumps(data)

    @web.authenticated
    def get(self):
        global DATA
        self.log.info(f"GET - {self.__class__}")
        if "MOCK" not in os.environ or os.environ["MOCK"] == "0":
            DATA = controller.list_my_running_jobs()
            self.log.info(json.dumps(DATA))
            if "MOCK" in os.environ:
                with open("./extensions/jupyterlab_orbit/jupyterlab_orbit/mockup/your_containers.json", "w") as outfile:
                    json.dump(DATA, outfile)
        else:
            path = Path(__file__).parent / "../mockup/your_containers.json"
            with open(path) as f:
                DATA = json.load(f)

        self.finish(self._dump())

    @web.authenticated
    def delete(self):
        global DATA
        input_data = self.get_json_body()
        job_name = input_data["name"]
        self.log.info(f"DELETE - {self.__class__} - %s", job_name)
        controller.delete_job(job_name)
        for c in DATA:
            if c["metadata"]["name"] == job_name:
                DATA.remove(c)

        self.finish(self._dump())
