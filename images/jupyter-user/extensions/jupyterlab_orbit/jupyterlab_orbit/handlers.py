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
from typing import Dict

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
from tornado import web

DATA: Dict[str, str] = {"foo": "foo description", "boo": "boo description", "bar": "bar description"}


class CatalogRouteHandler(APIHandler):
    @staticmethod
    def dump() -> str:
        return json.dumps([{"name": k, "description": v} for k, v in DATA.items()])

    @web.authenticated
    def get(self):
        self.log.info("GET - Catalog")
        self.finish(self.dump())

    @web.authenticated
    def delete(self):
        input_data = self.get_json_body()
        self.log.info("DELETE - Catalog - %s", input_data)
        DATA.pop(input_data["name"])
        self.finish(self.dump())


def setup_handlers(web_app):
    base_url: str = web_app.settings["base_url"]
    handlers = [(url_path_join(base_url, "jupyterlab_orbit", "catalog"), CatalogRouteHandler)]

    host_pattern: str = ".*$"
    web_app.add_handlers(host_pattern, handlers)
