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

TEAM_PVCS: List[Dict[str, str]] = []
CLUSTER_PVS: List[Dict[str, str]] = []
CLUSTER_STORAGECLASSES: List[Dict[str, str]] = []


class StorageRouteHandler(APIHandler):
    @staticmethod
    def _dump(slist, type) -> str:
        data: List[Dict[str, str]] = []
        for s in slist:
            pass
            storage: Dict[str, str] = dict()
            storage["name"] = s["metadata"]["name"]
            storage["creationTimestamp"] = s["metadata"]["creationTimestamp"]
            if type == "teampvc":
                storage["hint"] = json.dumps(s["spec"], indent=4)
                storage["size"] = s["spec"]["resources"]["requests"]["storage"]
            elif type == "clusterpv":
                storage["hint"] = json.dumps(s["spec"], indent=4)
                storage["size"] = s["spec"]["capacity"]["storage"]
            elif type == "clusterstorageclass":
                storage["hint"] = ""
                storage["provisioner"] = s["provisioner"]
            else:
                pass
            storage["info"] = s
            data.append(storage)
        data = sorted(
            data,
            key=lambda i: (i["creationTimestamp"] if "creationTimestamp" in i else i["name"]),
        )

        return json.dumps(data)

    @web.authenticated
    def get(self):
        self.log.debug("Entered storage GET")
        global TEAM_PVCS
        global CLUSTER_PVS
        global CLUSTER_STORAGECLASSES
        type: Optional[str] = self.get_argument("type", default="")
        self.log.info(f"GET - {self.__class__} - {type} {format}")
        if "MOCK" not in os.environ or os.environ["MOCK"] == "0":
            if type == "teampvc":
                self.log.debug("***teampvc***")
                TEAM_PVCS = controller.list_storage_pvc()
                data = TEAM_PVCS
            elif type == "clusterpv":
                self.log.debug("***clusterpv***")
                CLUSTER_PVS = controller.list_storage_pv()
                data = CLUSTER_PVS
            elif type == "clusterstorageclass":
                self.log.debug("***clusterstorageclass***")
                CLUSTER_STORAGECLASSES = controller.list_storage_class()
                data = CLUSTER_STORAGECLASSES
            else:
                raise Exception("Unknown type: %s", type)

            if "MOCK" in os.environ:
                with open(
                    f"{Path(__file__).parent.parent.parent}/test/mockup/storage-{type}.json",
                    "w",
                ) as outfile:
                    json.dump(data, outfile, indent=4)
        else:
            path = f"{Path(__file__).parent.parent.parent}/test/mockup/storage-{type}.json"
            self.log.info("Path: %s", path)
            with open(path) as f:
                if type == "teampvc":
                    TEAM_PVCS = json.load(f)
                    data = TEAM_PVCS
                elif type == "clusterpv":
                    CLUSTER_PVS = json.load(f)
                    data = CLUSTER_PVS
                elif type == "clusterstorageclass":
                    CLUSTER_STORAGECLASSES = json.load(f)
                    data = CLUSTER_STORAGECLASSES
                else:
                    raise Exception("Unknown type: %s", type)

        self.finish(self._dump(data, type))
        self.log.debug("Exit storage GET")

    @web.authenticated
    def delete(self):
        global TEAM_PVCS
        global CLUSTER_PVS
        input_data = self.get_json_body()
        name = input_data["name"]
        type: Optional[str] = self.get_argument("type", default="")
        self.log.info(f"DELETE - {self.__class__} - %s type: %s", name, type)
        if "MOCK" not in os.environ or os.environ["MOCK"] == "0":
            if type == "teampvc":
                response = controller.delete_storage_pvc(name)
            else:
                raise Exception("Unknown type: %s", type)
        else:
            if type == "teampvc":
                data = TEAM_PVCS
                TEAM_PVCS = [r for r in data if r["name"] != name]
            else:
                raise Exception("Unknown type: %s", type)

            response = {
                "status": "200",
                "reason": "OK",
                "message": f"Successfully deleted ={name}",
            }

        self.log.info(f"Delete response={response}")
        self.finish(json.dumps(response))
