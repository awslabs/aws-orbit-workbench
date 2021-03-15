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
from typing import Dict, List
import pprint
from aws_orbit_sdk.database import RedshiftUtils
from jupyter_server.base.handlers import APIHandler
from tornado import web

DATA: List[Dict[str, str]] = []


class RedshiftRouteHandler(APIHandler):
    def _dump(self) -> str:
        data = []
        pprint.pprint(DATA)
        for cid, cdetails in DATA.keys():
            ddirct = {
             "name": cdetails['Name'],
             "cluster_id": cdetails['cluster_id'],
             "state": cdetails["ClusterStatus"],
             "nodetype": cdetails["instances"]["NodeType"]
            }
            data.append(ddirct)
        pprint.pprint(data)
        #self.log.info(json.dumps(DATA))
        return json.dumps(data)

    def sdk_get_team_clusters(self):
        pass

    @web.authenticated
    def get(self):
        global DATA
        rs = RedshiftUtils()
        DATA = rs.get_team_clusters()
        self.log.info("************")
        self.log.info(f"GET - {self.__class__}")
        self.finish(self._dump())

    # @web.authenticated
    # def delete(self):
    #     global DATA
    #     input_data = self.get_json_body()
    #     self.log.info(f"DELETE - {self.__class__} - %s", input_data)
    #     DATA.pop(input_data["name"])
    #     self.finish(self._dump())
