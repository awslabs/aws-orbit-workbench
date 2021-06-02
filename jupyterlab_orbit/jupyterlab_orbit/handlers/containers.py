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
from datetime import datetime
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
    def _dump_job(clist, type) -> str:
        data: List[Dict[str, str]] = []
        for c in clist:
            container: Dict[str, str] = dict()
            container["name"] = c["metadata"]["name"]
            container["job_name"] = c["metadata"]["name"]
            if type == "cron":
                job_template = c["spec"]["jobTemplate"]["spec"]["template"]
                container["time"] = c["spec"]["schedule"]
                container["job_state"] = "active"

            envs = job_template["spec"]["containers"][0]["env"]

            tasks = json.loads([e["value"] for e in envs if e["name"] == "tasks"][0])
            container["hint"] = json.dumps(tasks, indent=4)
            container["tasks"] = tasks["tasks"]

            if "labels" in c["metadata"]:
                container["node_type"] = (
                    c["metadata"]["labels"]["orbit/node-type"]
                    if "orbit/node-type" in c["metadata"]["labels"]
                    else "unknown"
                )

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
            data,
            key=lambda i: (
                i["rank"],
                i["creationTimestamp"] if "creationTimestamp" in i else i["name"],
            ),
        )

        return json.dumps(data)

    @staticmethod
    def _dump_pod(clist) -> str:
        data: List[Dict[str, str]] = []
        for c in clist:
            container: Dict[str, str] = dict()
            container["name"] = c["metadata"]["name"]
            if "app" in c["metadata"]["labels"]:
                container["pod_app"] = c["metadata"]["labels"]["app"]
                if "emr-spark" == c["metadata"]["labels"]["app"]:
                    container["job_name"] = c["metadata"]["labels"]["emr-containers.amazonaws.com/job.id"]
                else:
                    container["job_name"] = c["metadata"]["labels"]["job-name"]

            container["time"] = c["metadata"]["creationTimestamp"]
            response_datetime_format = "%Y-%m-%dT%H:%M:%SZ"

            if "status" in c:
                # Succeeded / Completed
                constainer_phase_status = (c["status"]["phase"]).lower()
                if constainer_phase_status in ["succeeded", "failed"]:
                    if container["pod_app"] == "emr-spark":
                        container_status = [
                            cs for cs in c["status"]["containerStatuses"] if "spark-kubernetes-driver" == cs["name"]
                        ][0]
                    else:
                        container_status = c["status"]["containerStatuses"][0]

                    completion_dt = datetime.strptime(
                        container_status["state"]["terminated"]["finishedAt"],
                        response_datetime_format,
                    )
                    start_dt = datetime.strptime(
                        container_status["state"]["terminated"]["startedAt"],
                        response_datetime_format,
                    )
                    duration = completion_dt - start_dt
                    container["duration"] = str(duration)
                    container["completionTime"] = (
                        container_status["state"]["terminated"]["finishedAt"]
                        if constainer_phase_status == "succeeded"
                        else ""
                    )
                    container["job_state"] = constainer_phase_status
                elif constainer_phase_status == "running":
                    started_at = datetime.strptime(c["status"]["startTime"], response_datetime_format)
                    duration = datetime.utcnow() - started_at
                    container["duration"] = str(duration).split(".")[0]
                    container["completionTime"] = ""
                    container["job_state"] = constainer_phase_status
                else:
                    container["completionTime"] = ""
                    container["duration"] = ""
                    container["job_state"] = "unknown"
            else:
                container["completionTime"] = ""
                container["duration"] = ""
                container["job_state"] = "unknown"

            if container["pod_app"] == "emr-spark":
                container_task = [ct for ct in c["spec"]["containers"] if "spark-kubernetes-driver" == ct["name"]][0]
                container["hint"] = json.dumps(container_task, indent=4)
                container["tasks"] = container_task["args"]
                container["notebook"] = container_task["args"][-2].split("/")[-1]
                container["container_name"] = "spark-kubernetes-driver"
            else:
                envs = c["spec"]["containers"][0]["env"]
                tasks = json.loads([e["value"] for e in envs if e["name"] == "tasks"][0])
                container["hint"] = json.dumps(tasks, indent=4)
                container["tasks"] = tasks["tasks"]
                container["notebook"] = (
                    tasks["tasks"][0]["notebookName"]
                    if "notebookName" in tasks["tasks"][0]
                    else f'{tasks["tasks"][0]["moduleName"]}.{tasks["tasks"][0]["functionName"]}'
                )
                container["container_name"] = ""
            if "labels" in c["metadata"]:
                container["node_type"] = (
                    c["metadata"]["labels"]["orbit/node-type"]
                    if "orbit/node-type" in c["metadata"]["labels"]
                    else "unknown"
                )
                container["job_type"] = (
                    c["metadata"]["labels"]["app"] if "app" in c["metadata"]["labels"] else "unknown"
                )
            if container["job_state"] == "running":
                container["rank"] = 1
            else:
                container["rank"] = 2
            container["info"] = c
            data.append(container)
        data = sorted(
            data,
            key=lambda i: (
                i["rank"],
                i["creationTimestamp"] if "creationTimestamp" in i else i["name"],
            ),
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
                MYJOBS = controller.list_my_running_pods()
                data = MYJOBS
                self.finish(self._dump_pod(data))
            elif type == "team":
                TEAMJOBS = controller.list_team_running_pods()
                data = TEAMJOBS
                self.finish(self._dump_pod(data))
            elif type == "cron":
                CRONJOBS = controller.list_running_cronjobs()
                data = CRONJOBS
                self.finish(self._dump_job(data, type))
            else:
                raise Exception("Unknown type: %s", type)
            if "MOCK" in os.environ:
                with open(
                    f"{Path(__file__).parent.parent.parent}/test/mockup/containers-{type}.json",
                    "w",
                ) as outfile:
                    json.dump(data, outfile, indent=4)
        else:
            path = f"{Path(__file__).parent.parent.parent}/test/mockup/containers-{type}.json"
            self.log.info("Path: %s", path)
            with open(path) as f:
                if type == "user":
                    MYJOBS = json.load(f)
                    self.finish(self._dump_pod(MYJOBS))
                elif type == "team":
                    TEAMJOBS = json.load(f)
                    self.finish(self._dump_pod(TEAMJOBS))
                elif type == "cron":
                    CRONJOBS = json.load(f)
                    self.finish(self._dump_job(CRONJOBS, type))
                else:
                    raise Exception("Unknown type: %s", type)

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
        name = input_data["name"]
        job_type: Optional[str] = self.get_argument("type", default="")
        self.log.info(f"DELETE - {self.__class__} - %s type: %s", name, job_type)
        if job_type == "user":
            controller.delete_pod(name)
            data = MYJOBS
            self._delete(name, data)
            self.finish(self._dump_pod(data, type))
        elif job_type == "team":
            controller.delete_pod(name)
            data = TEAMJOBS
            self._delete(name, data)
            self.finish(self._dump_pod(data, type))
        elif job_type == "cron":
            controller.delete_cronjob(name)
            data = CRONJOBS
            self._delete(name, data)
            self.finish(self._dump_job(data, type))
        else:
            raise Exception("Unknown job_type: %s", job_type)
