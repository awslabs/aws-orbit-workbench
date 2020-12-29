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
from datetime import date, datetime
from typing import Any, Dict, Optional

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def json_serial(obj: Any) -> str:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
    logger.info(f"Lambda metadata: {json.dumps(event)} (type = {type(event)})")

    name = event.get("name", None)
    if name is None:
        raise ValueError("Invalid 'name': %s", name)

    eks = boto3.client("eks")
    return json.loads(json.dumps(eks.describe_cluster(name=name), default=json_serial))
