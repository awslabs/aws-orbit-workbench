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

from aws_orbit import sh, utils
from aws_orbit.plugins import hooks

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger("aws_orbit")
POD_FILENAME = os.path.join(os.path.dirname(__file__), "job_definition.yaml")


@hooks.deploy
def deploy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    configmap_script_name = f"{plugin_id}-script"
    vars = dict(
        team=team_context.name,
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        tag=context.images.jupyter_hub.version,
        restart_policy=parameters["restartPolicy"] if "restartPolicy" in parameters else "Never",
        plugin_id=plugin_id,
        toolkit_s3_bucket=context.toolkit.s3_bucket,
    )

    if "script" in parameters:
        script_body = parameters["script"]
    else:
        raise Exception(f"Plugin {plugin_id} must define parameter 'script'")
    script_file = os.path.join(os.path.dirname(POD_FILENAME), f"{plugin_id}-script.sh")

    script_body = utils.resolve_parameters(script_body, cast(Dict[str, str], vars))
    with open(script_file, "w") as file:
        file.write(script_body)

    _logger.debug(script_body)
    # Cleanup of previous installation if needed
    sh.run(f"kubectl delete jobs/team-script-{plugin_id} --namespace {team_context.name} --ignore-not-found")
    sh.run(f"kubectl delete configmap {configmap_script_name} --namespace {team_context.name} --ignore-not-found")

    # Create the configmap with the script
    sh.run(
        f"kubectl create configmap {configmap_script_name} --from-file={script_file} --namespace {team_context.name}"
    )
    _logger.debug(f"Create config map: {configmap_script_name} at namespace {team_context.name}")

    _logger.debug(
        "Using S3 Sync Pod at %s for Env name: %s | Team name: %s",
        POD_FILENAME,
        context.name,
        team_context.name,
    )
    input = POD_FILENAME
    output = os.path.join(os.path.dirname(POD_FILENAME), f"{plugin_id}-team.yaml")

    with open(input, "r") as file:
        content: str = file.read()

    content = utils.resolve_parameters(content, cast(Dict[str, str], vars))

    _logger.debug("Kubectl Team %s context:\n%s", team_context.name, content)
    with open(output, "w") as file:
        file.write(content)

    # run the POD to execute the script
    cmd = f"kubectl apply -f {output}  --namespace {team_context.name}"
    _logger.debug(cmd)
    sh.run(cmd)


@hooks.destroy
def destroy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Delete Plugin %s of Team Env name: %s | Team name: %s", plugin_id, context.name, team_context.name)
    sh.run(f"kubectl delete jobs/team-script-{plugin_id} --namespace {team_context.name} --ignore-not-found")
    sh.run(f"kubectl delete configmap {plugin_id}-script --namespace {team_context.name} --ignore-not-found")
