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
from typing import Dict, List, Any

from jupyter_server.base.handlers import APIHandler
from tornado import web

DATA: Dict[str, List[Any]] = {
    "dataSource": [
        {
            "key": "1",
            "name": "Mike",
            "age": 32,
            "address": "10 Downing Street",
        },
        {
            "key": "2",
            "name": "John",
            "age": 42,
            "address": "10 Downing Street",
        },
    ],
    "columns": [
        {
            "title": 'Name',
            "dataIndex": 'name',
            "key": 'name',
        },
        {
            "title": 'Age',
            "dataIndex": 'age',
            "key": 'age',
        },
        {
            "title": 'Address',
            "dataIndex": 'address',
            "key": 'address',
        }
    ]
}


class TableRouteHandler(APIHandler):
    @web.authenticated
    def get(self):
        self.log.info(f"GET - {self.__class__}")
        self.finish(json.dumps(DATA))
