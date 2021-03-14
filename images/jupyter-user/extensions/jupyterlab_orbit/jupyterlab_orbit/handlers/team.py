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

from aws_orbit_sdk.common import get_workspace
from jupyter_server.base.handlers import APIHandler
from tornado import web

DATA: List[Dict[str, str]] = []


class TeamRouteHandler(APIHandler):
    @staticmethod
    def _dump(data) -> str:
        data: List[Dict[str, str]] = []
        data.append({'namm':'foo','value': 'bar'})
        return json.dumps(data)

    @web.authenticated
    def get(self):
        global DATA
        self.log.info(f"GET - {self.__class__}")
        DATA = get_workspace()
        # hide some details
        if 'Elbs' in DATA:
            del DATA['Elbs']
        if 'Plugins' in DATA:
            del DATA['Plugins']
        if "MOCK" not in os.environ or os.environ["MOCK"] == "0":
            if "MOCK" in os.environ:
                path = Path(__file__).parent / f"../mockup/team.json", "w"
                self.log.info(f"writing mockup data to {path}")
                with open(
                        path
                ) as outfile:
                    json.dump(data, outfile, indent=4)
        else:
            path = Path(__file__).parent / f"../mockup/team.json"
            DATA = json.load(f)

            with open(path) as f:
                DATA = json.load(f)

        self.finish(self._dump(DATA))
