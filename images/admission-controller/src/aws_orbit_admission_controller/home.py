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


from typing import Any, Dict, Optional, cast
from flask import Flask, render_template,request
import logging
import json

def login(logger: logging.Logger, app: Flask) -> Any:
    logger.debug("cookies: %s", json.dumps(request.cookies))
    return render_template('index.html', title='login')

def logout(logger: logging.Logger, app: Flask) -> Any:
    logger.debug("cookies: %s", json.dumps(request.cookies))
    logger.debug("headers: %s", json.dumps(dict(request.headers)))
    logger.debug("authorization: %s", json.dumps(request.authorization))

    return render_template('index.html', title='logout')