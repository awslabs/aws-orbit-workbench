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
import os
from typing import TYPE_CHECKING, Any, Dict

from aws_orbit import sh, utils
from aws_orbit.plugins import hooks
import aws_orbit.services.cfn as cfn

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger("aws_orbit")
POD_FILENAME = os.path.join(os.path.dirname(__file__), "job_definition.yaml")


@hooks.deploy
def deploy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    if parameters['cfn_template_path'] and os.path.isfile(parameters['cfn_template_path']):
        _logger.info(f"CloudFormation template found at {parameters['cfn_template_path']}")
    else:
        raise FileNotFoundError(f"CloudFormation template not found at {parameters['cfn_template_path']}")

    # Read the YAML/JSON file from the parameters key
    # Replace the ${} references with any requierd variables
    # aws_orbit.services.
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    cfn.deploy_template(
        stack_name =  f"orbit-{context.name}-{team_context.name}-{plugin_id}-custom-resources",
        filename = parameters['cfn_template_path'],
        env_tag = context.env_tag,
        s3_bucket = context.toolkit.s3_bucket
    )



@hooks.destroy
def destroy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    cfn.destroy_stack(stack_name = f"orbit-{context.name}-{team_context.name}-{plugin_id}-custom-resources")

