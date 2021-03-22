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
from typing import Any, Dict, List

from aws_orbit_sdk import glue_catalog
from jupyter_server.base.handlers import APIHandler
from tornado import web

DATA: List[Dict[str, Any]] = []

DATA2: Dict[str, Any] = {}


class CatalogRouteHandler(APIHandler):
    @web.authenticated
    def get(self):
        self.log.info(f"GET - {self.__class__}")
        global DATA
        DATA = glue_catalog.getCatalogAsDict()
        self.log.info(f"GET - {self.__class__}")
        self.finish(json.dumps(DATA))
