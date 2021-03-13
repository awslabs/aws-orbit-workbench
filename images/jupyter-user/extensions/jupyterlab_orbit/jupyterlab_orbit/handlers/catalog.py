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
from typing import Any, Dict, List, Optional

from aws_orbit_sdk import glue_catalog
from jupyter_server.base.handlers import APIHandler
from tornado import web

MYJOBS: Dict[str, str] = {"foo": "foo description", "boo1": "boo description", "bar": "bar description"}

DATA2: List[Dict[str, Any]] = [
    {
        "title": "Database A",
        "key": "0-0",
        "children": [
            {
                "title": "Table A",
                "key": "0-0-0",
                "children": [
                    {
                        "title": "Column A",
                        "key": "0-0-0-0",
                    },
                    {
                        "title": "Column B",
                        "key": "0-0-0-1",
                    },
                ],
            }
        ],
    },
    {
        "title": "Database B",
        "key": "1-0",
        "children": [
            {
                "title": "Table A",
                "key": "1-0-0",
                "children": [
                    {
                        "title": "Column A",
                        "key": "1-0-0-0",
                    },
                    {
                        "title": "Column B",
                        "key": "1-0-0-1",
                    },
                ],
            }
        ],
    },
]


class CatalogRouteHandler(APIHandler):
    @staticmethod
    def dump() -> str:
        return json.dumps([{"name": k, "description": v} for k, v in MYJOBS.items()])

    @web.authenticated
    def get(self):
        self.log.info(f"GET - {self.__class__}")
        self.finish(self.dump())

    @web.authenticated
    def delete(self):
        input_data = self.get_json_body()
        self.log.info(f"DELETE - {self.__class__} - %s", input_data)
        MYJOBS.pop(input_data["name"])
        self.finish(self.dump())


class TreeRouteHandler(APIHandler):
    @web.authenticated
    def get(self):
        self.log.info("GET - Tree")
        global DATA2
        DATA2 = glue_catalog.getCatalogAsDict()

        self.log.info(f"GET - {self.__class__}")
        self.finish(json.dumps(DATA2))
