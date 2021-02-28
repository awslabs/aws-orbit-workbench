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
from typing import TYPE_CHECKING, Any, Dict, cast

import aws_orbit.services.cfn as cfn
import aws_orbit.services.ssm as ssm
from aws_orbit.plugins import hooks

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger("aws_orbit")


@hooks.pre
def deploy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    if parameters["cfn_template_path"] and os.path.isfile(parameters["cfn_template_path"]):
        _logger.info(f"CloudFormation template found at {parameters['cfn_template_path']}")
    else:
        raise FileNotFoundError(f"CloudFormation template not found at {parameters['cfn_template_path']}")

    # Read the YAML/JSON file from the parameters key
    # Replace the ${} references with any required variables
    # aws_orbit.services.
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    context.user_pool_id
    # MYTODO Can push kms key arn to context instead of reading from SSM
    env_kms_arn = cast(str, ssm.get_parameter(name=context.demo_ssm_parameter_name)["KMSKey"])
    cfn.deploy_synth_template(
        stack_name=f"orbit-{context.name}-{team_context.name}-{plugin_id}-custom-demo-resources",
        filename=parameters["cfn_template_path"],
        env_tag=context.env_tag,
        s3_bucket=context.toolkit.s3_bucket,
        synth_params={
            "env_name": context.name,
            "deploy_id": cast(str, context.toolkit.deploy_id),
            "env_kms_arn": env_kms_arn,
            "cognito_user_pool_id": cast(str, context.user_pool_id),
        },
    )


@hooks.post
def destroy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    _logger.debug("**********Destroying custom resources using post hook")
    cfn.destroy_stack(stack_name=f"orbit-{context.name}-{team_context.name}-{plugin_id}-custom-demo-resources")
