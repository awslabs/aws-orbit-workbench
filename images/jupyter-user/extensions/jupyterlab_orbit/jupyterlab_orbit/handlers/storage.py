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

TEAMPVCS: List[Dict[str, str]] = []
ALLPVCS: List[Dict[str, str]] = []

class StorageRouteHandler(APIHandler):
    @staticmethod
    def _dump(pvclist, type) -> str:
        data = sorted(
            pvclist, key=lambda i: (i["metadata"]["creationTimestamp"]
                                    if "creationTimestamp" in i["metadata"]
                                    else i["metadata"]["name"])
        )

        return json.dumps(data)

    @web.authenticated
    def get(self):
        self.log.debug("Entered storage GET")
        global TEAMPVCS
        type: Optional[str] = self.get_argument("type", default="")
        self.log.info(f"GET - {self.__class__} - {type} {format}")
        if "MOCK" not in os.environ or os.environ["MOCK"] == "0":
            if type == "team":
                TEAMPVCS = controller.list_storage_pvc(all=False)
                data = TEAMPVCS
            elif type == "all":
                ALLPVCS = controller.list_storage_pvc(all=True)
                data = ALLPVCS
            else:
                raise Exception("Unknown type: %s", type)
                #TEAMPVCS = controller.list_storage_pvc(all=False)
                #data = TEAMPVCS

            if "MOCK" in os.environ:
                with open(f"{Path(__file__).parent.parent.parent}/test/mockup/storage-pvc-{type}.json", "w") as outfile:
                    json.dump(data, outfile, indent=4)
        else:
            path = f"{Path(__file__).parent.parent.parent}/test/mockup/storage-pvc-{type}.json"
            self.log.info("Path: %s", path)
            with open(path) as f:
                if type == "team":
                    TEAMPVCS = json.load(f)
                    data = TEAMPVCS
                elif type == "all":
                    ALLPVCS = json.load(f)
                    data = ALLPVCS
                else:
                    raise Exception("Unknown type: %s", type)

        self.finish(self._dump(data, type))
        self.log.debug("Exit storage GET")


