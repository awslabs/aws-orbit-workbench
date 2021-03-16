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
        for cid, cdetails in DATA.items():
            ddirct = {
             "name": cdetails['Name'],
             "hint": json.dumps(cdetails["info"]["Endpoint"], indent=4),
             "state": cdetails["info"]["ClusterStatus"],
             "start_time": str(cdetails["info"]["ClusterCreateTime"].strftime("%Y-%m-%d %H:%M %Z")),
             "node_type": cdetails["instances"]["node_type"],
             "nodes": cdetails["instances"]["nodes"]
            }
            data.append(ddirct)
        pprint.pprint(data)
        #self.log.info(json.dumps(DATA))
        return json.dumps(data, default=str)

    def sdk_get_team_clusters(self):
        pass

    @web.authenticated
    def get(self):
        global DATA
        DATA = RedshiftUtils().get_team_clusters()
        self.log.info(f"GET - {self.__class__}")
        self.finish(self._dump())

    @web.authenticated
    def delete(self):
        global DATA
        input_data = self.get_json_body()
        self.log.info(f"DELETE - {self.__class__} - %s", input_data)
        RedshiftUtils().delete_redshift_cluster(cluster_name=input_data["name"])
        DATA = RedshiftUtils().get_team_clusters()
        self.finish(self._dump())
