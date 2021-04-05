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

from typing import Optional

from aws_orbit_sdk.database import AthenaUtils
from jupyter_server.base.handlers import APIHandler
from tornado import web

athena = AthenaUtils()


class AthenaRouteHandler(APIHandler):
    @web.authenticated
    def get(self):

        database: Optional[str] = self.get_argument("database", default="")
        table: Optional[str] = self.get_argument("table", default="")
        field: Optional[str] = self.get_argument("field", default="")
        direction: Optional[str] = self.get_argument("direction", default="")
        sample_size = 100

        json_data = athena.get_sample_data(
            database=database,
            table=table,
            sample=sample_size,
            field=field,
            direction=direction,
        )

        self.log.info(f"GET - {self.__class__}")
        self.finish(json_data)
