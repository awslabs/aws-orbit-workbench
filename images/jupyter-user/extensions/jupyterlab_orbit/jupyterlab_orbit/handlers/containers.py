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

MYJOBS: List[Dict[str, str]] = []
TEAMJOBS: List[Dict[str, str]] = []
CRONJOBS: List[Dict[str, str]] = []


class ContainersRouteHandler(APIHandler):
    @staticmethod
    def _dump(clist, type) -> str:
        data: List[Dict[str, str]] = []
        for c in clist:
            container: Dict[str, str] = dict()
            container["name"] = c["metadata"]["name"]
            if type == "cron":
                job_template = c["spec"]["jobTemplate"]["spec"]["template"]
                container["time"] = c["spec"]["schedule"]
            else:
                job_template = c["spec"]["template"]
                container["time"] = c["metadata"]["creationTimestamp"]

            envs = job_template["spec"]["containers"][0]["env"]
            tasks = json.loads([e["value"] for e in envs if e["name"] == "tasks"][0])
            container["hint"] = json.dumps(tasks, indent=4)
            container["tasks"] = tasks

            if "labels" in c["metadata"] and "orbit/node-type" in c["metadata"]["labels"]:
                container["node_type"] = c["metadata"]["labels"]["orbit/node-type"]
            else:
                container["node_type"] = "unknown"

            if "status" in c:
                if "failed" in c["status"] and c["status"]["failed"] == 1:
                    container["job_state"] = "failed"
                elif "active" in c["status"] and c["status"]["active"] == 1:
                    container["job_state"] = "running"
                elif "succeeded" in c["status"] and c["status"]["succeeded"] == 1:
                    container["job_state"] = "succeeded"
                else:
                    container["job_state"] = "unknown"
            else:
                container["job_state"] = "unknown"

            container["info"] = c
            data.append(container)
        return json.dumps(data)

    @web.authenticated
    def get(self):
        global MYJOBS
        type: Optional[string] = self.get_argument("type", default="")
        self.log.info(f"GET - {self.__class__} - {type} {format}")
        if "MOCK" not in os.environ or os.environ["MOCK"] == "0":
            if type == "user":
                MYJOBS = controller.list_my_running_jobs()
                data = MYJOBS
            elif type == "team":
                TEAMJOBS = controller.list_team_running_jobs()
                data = TEAMJOBS
            elif type == "cron":
                CRONJOBS = controller.list_running_cronjobs()
                data = CRONJOBS
            else:
                raise Exception("Unknown type: %s", type)
            # self.log.info(json.dumps(DATA))
            if "MOCK" in os.environ:
                with open(
                    f"./extensions/jupyterlab_orbit/jupyterlab_orbit/mockup/containers-{type}.json", "w"
                ) as outfile:
                    json.dump(data, outfile, indent=4)
        else:
            path = Path(__file__).parent / f"../mockup/containers-{type}.json"
            with open(path) as f:
                if type == "user":
                    MYJOBS = json.load(f)
                    data = MYJOBS
                elif type == "team":
                    TEAMJOBS = json.load(f)
                    data = TEAMJOBS
                elif type == "cron":
                    CRONJOBS = json.load(f)
                    data = CRONJOBS
                else:
                    raise Exception("Unknown type: %s", type)

        self.finish(self._dump(data, type))

    @staticmethod
    def _delete(job_name, data):
        for c in data:
            if c["metadata"]["name"] == job_name:
                MYJOBS.remove(c)

    @web.authenticated
    def delete(self):
        global MYJOBS
        input_data = self.get_json_body()
        job_name = input_data["name"]
        type: Optional[string] = self.get_argument("type", default="")
        self.log.info(f"DELETE - {self.__class__} - %s", job_name)
        if type == "user":
            MYJOBS = controller.delete_job(job_name)
            data = MYJOBS
        elif type == "team":
            TEAMJOBS = controller.delete_job(job_name)
            data = TEAMJOBS
        elif type == "cron":
            CRONJOBS = controller.delete_cronjob(job_name)
            data = CRONJOBS
        else:
            raise Exception("Unknown type: %s", type)

        _delete(job_name, data)
        self.finish(self._dump())
