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
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
    logger.info(f"Lambda metadata: {json.dumps(event)} (type = {type(event)})")

    namespace = event.get("Namespace")
    api = event.get("ExecutionInput", {}).get("Api")
    version = event.get("ExecutionInput", {}).get("Version", "v1")
    path = event.get("ExecutionInput", {}).get("Path")
    path_args = event.get("ExecutionInput", {}).get("PathArgs")
    method = event.get("ExecutionInput", {}).get("Method", "GET")
    query_parameters = event.get("ExecutionInput", {}).get("QueryParameters")
    request_body = event.get("ExecutionInput", {}).get("RequestBody")

    if namespace is None or path is None:
        raise ValueError("Parameters 'Namespace' and 'Path' are required")

    api = f"apis/{api}" if api else "api"
    base_path = f"/{api}/{version}/namespaces/{namespace}"
    path = path.format(**path_args) if path_args else path
    full_path = base_path + path
    logger.info(f"Reqeust: {method} {full_path}")
    return {"Path": full_path, "Method": method, "QueryParameters": query_parameters, "RequestBody": request_body}
