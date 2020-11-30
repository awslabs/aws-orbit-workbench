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

import logging
import json
from typing import TYPE_CHECKING, Dict

# if TYPE_CHECKING:
#     from datamaker_cli.manifest import Manifest
#
# _logger: logging.Logger = logging.getLogger(__name__)
#
# def write_ssm(manifest:Manifest,ssm_parameter_name:str,ssm_payload:Dict) -> None:
#     client = manifest.boto3_client("ssm")
#     _logger.debug("Writing manifest to SSM parameter.")
#     try:
#         client.get_parameter(Name=ssm_parameter_name)["Parameter"]["Value"]
#         exists: bool = True
#     except client.exceptions.ParameterNotFound:
#         exists = False
#     _logger.debug("Does Manifest SSM parameter exist? %s", exists)
#     if exists:
#         client.put_parameter(
#             Name=ssm_parameter_name,
#             Value=str(json.dumps(obj=ssm_payload, sort_keys=True)),
#             Overwrite=True,
#             Tier="Intelligent-Tiering",
#         )
