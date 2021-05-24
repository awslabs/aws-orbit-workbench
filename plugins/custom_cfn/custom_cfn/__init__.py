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

from aws_orbit.plugins import hooks
from aws_orbit.plugins.helpers import cdk_deploy
from aws_orbit.services import cfn, s3

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger("aws_orbit")

ORBIT_CUSTOM_CFN_ROOT = os.path.dirname(os.path.abspath(__file__))


@hooks.pre
def deploy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug(
        "Deploying Custom CloudFormation plugin resources for team %s",
        team_context.name,
    )
    if parameters["CfnTemplatePath"] and os.path.isfile(parameters["CfnTemplatePath"]):
        _logger.info(f"CloudFormation template found at {parameters['CfnTemplatePath']}")
    else:
        raise FileNotFoundError(f"CloudFormation template not found at {parameters['CfnTemplatePath']}")

    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    cfn_params: Dict[str, Any] = {
        "envname": context.name,
        "envdeployid": cast(str, context.toolkit.deploy_id),
        "envcognitouserpoolid": cast(str, context.user_pool_id),
    }
    cfn_params.update(parameters)
    _logger.debug(f"cfn_params={cfn_params}")
    cdk_deploy(
        stack_name=f"orbit-{context.name}-{team_context.name}-{plugin_id}-custom-demo-resources",
        app_filename=os.path.join(ORBIT_CUSTOM_CFN_ROOT, "cdk.py"),
        context=context,
        team_context=team_context,
        parameters=cfn_params,
    )
    _logger.debug("Custom Cfn plugin pre_hook compeleted")


@hooks.post
def destroy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug(
        "Destroying Custom CloudFormation  plugin resources for team %s",
        team_context.name,
    )
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    env_name = context.name
    acct: str = context.account_id
    deploy_id: str = cast(str, context.toolkit.deploy_id)
    plugin_id = plugin_id.replace("_", "-")
    stack_name = f"orbit-{context.name}-{team_context.name}-{plugin_id}-custom-demo-resources"
    _logger.debug(f"stack_name={stack_name}")
    bucket_names: Dict[str, Any] = {
        "lake-bucket": f"orbit-{env_name}-demo-lake-{acct}-{deploy_id}",
        "secured-lake-bucket": f"orbit-{env_name}-secured-demo-lake-{acct}-{deploy_id}",
    }
    _logger.debug(f"bucket_names={bucket_names}")
    # CDK skips bucket deletion.
    if cfn.does_stack_exist(stack_name=stack_name):
        try:
            _logger.debug("Deleting lake-bucket")
            s3.delete_bucket(bucket=bucket_names["lake-bucket"])
        except Exception as ex:
            _logger.debug("Skipping Team Lake Bucket deletion. Cause: %s", ex)
        try:
            _logger.debug("Deleting secured-lake-bucket")
            s3.delete_bucket(bucket=bucket_names["secured-lake-bucket"])
        except Exception as ex:
            _logger.debug("Skipping Team Secured Lake Bucket deletion. Cause: %s", ex)

    _logger.debug("Destroying custom resources using post hook")
    cfn.destroy_stack(stack_name=stack_name)
    _logger.debug("Destroyed")
