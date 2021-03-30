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
from typing import Dict, List, Optional

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
                container["job_state"] = "active"
            else:
                job_template = c["spec"]["template"]
                container["time"] = c["metadata"]["creationTimestamp"]
                if "status" in c and "completionTime" in c["status"]:
                    container["completionTime"] = c["status"]["completionTime"]
                else:
                    container["completionTime"] = ""
                if "status" in c:
                    if "failed" in c["status"] and c["status"]["failed"] == 1:
                        container["job_state"] = "failed"
                    elif "active" in c["status"] and c["status"]["active"] == 1:
                        container["job_state"] = "running"
                    elif "succeeded" in c["status"] and c["status"]["succeeded"] == 1:
                        container["job_state"] = "succeeded"
                    else:
                        container["job_state"] = "unknown"
            envs = job_template["spec"]["containers"][0]["env"]
            tasks = json.loads([e["value"] for e in envs if e["name"] == "tasks"][0])
            container["hint"] = json.dumps(tasks, indent=4)
            container["tasks"] = tasks["tasks"]

            if "labels" in c["metadata"] and "orbit/node-type" in c["metadata"]["labels"]:
                container["node_type"] = c["metadata"]["labels"]["orbit/node-type"]
            else:
                container["node_type"] = "unknown"

            container["notebook"] = (
                tasks["tasks"][0]["notebookName"]
                if "notebookName" in tasks["tasks"][0]
                else f'{tasks["tasks"][0]["moduleName"]}.{tasks["tasks"][0]["functionName"]}'
            )
            if container["job_state"] == "running":
                container["rank"] = 1
            else:
                container["rank"] = 2
            container["info"] = c
            data.append(container)

        data = sorted(
            data, key=lambda i: (i["rank"], i["creationTimestamp"] if "creationTimestamp" in i else i["name"])
        )

        return json.dumps(data)

    @web.authenticated
    def get(self):
        global MYJOBS
        global TEAMJOBS
        global CRONJOBS
        type: Optional[str] = self.get_argument("type", default="")
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
            if "MOCK" in os.environ:
                with open(f"{Path(__file__).parent.parent.parent}/test/mockup/containers-{type}.json", "w") as outfile:
                    json.dump(data, outfile, indent=4)
        else:
            path = f"{Path(__file__).parent.parent.parent}/test/mockup/containers-{type}.json"
            self.log.info("Path: %s", path)
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
                data.remove(c)

    @web.authenticated
    def delete(self):
        global MYJOBS
        global TEAMJOBS
        global CRONJOBS
        input_data = self.get_json_body()
        job_name = input_data["name"]
        job_type: Optional[str] = self.get_argument("type", default="")
        self.log.info(f"DELETE - {self.__class__} - %s type: %s", job_name, job_type)
        if job_type == "user":
            controller.delete_job(job_name)
            data = MYJOBS
        elif job_type == "team":
            controller.delete_job(job_name)
            data = TEAMJOBS
        elif job_type == "cron":
            controller.delete_cronjob(job_name)
            data = CRONJOBS
        else:
            raise Exception("Unknown job_type: %s", job_type)

        self._delete(job_name, data)
        self.finish(self._dump(data, type))
