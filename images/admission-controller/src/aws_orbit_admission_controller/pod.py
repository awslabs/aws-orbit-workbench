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

import base64
import copy
import logging
import random
from typing import Any, Dict

import jsonpatch
# from aws_orbit_admission_controller import load_config
from flask import jsonify


def process_request(logger: logging.Logger, request: Dict[str, Any]) -> Any:
    spec = request["object"]
    modified_spec = copy.deepcopy(spec)

    logger.info("request: %s", request)

    try:
        modified_spec["metadata"]["labels"]["example.com/new-label"] = str(random.randint(1, 1000))
    except KeyError:
        pass

    patch = jsonpatch.JsonPatch.from_diff(spec, modified_spec)
    return jsonify(
        {
            "response": {
                "allowed": True,
                "uid": request["uid"],
                "patch": base64.b64encode(str(patch).encode()).decode(),
                "patchtype": "JSONPatch",
            }
        }
    )
