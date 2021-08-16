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
from typing import TYPE_CHECKING, Any, Dict, Optional

import yaml
from aws_orbit.plugins import hooks
from aws_orbit.remote_files import helm

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext
_logger: logging.Logger = logging.getLogger("aws_orbit")
CHART_PATH = os.path.join(os.path.dirname(__file__))


@hooks.deploy
def deploy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    chart_path = helm.create_team_charts_copy(team_context=team_context, path=CHART_PATH, target_path=plugin_id)
    containers = parameters["replicas"] if "replicas" in parameters else 1
    del parameters["replicas"]
    if "cpu" not in parameters:
        parameters["cpu"] = "1"

    if "node_group" not in parameters:
        raise Exception(f"The parameter 'node_group' is missing for {plugin_id}...please add it")

    node_group = parameters["node_group"]
    del parameters["node_group"]

    resources = {"resources": parameters}

    _logger.info(f"overprovisioning installed with {containers} containers of resources:  {resources}.")

    vars: Dict[str, Optional[str]] = dict(
        team=team_context.name,
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        restart_policy=parameters["restartPolicy"] if "restartPolicy" in parameters else "Never",
        plugin_id=plugin_id,
        containers=containers,
        resources=yaml.dump(resources),
        toolkit_s3_bucket=context.toolkit.s3_bucket,
        node_group=node_group,
    )

    repo = team_context.name
    chart_name, chart_version, chart_package = helm.package_chart(repo=repo, chart_path=chart_path, values=vars)
    helm.install_chart(
        repo=repo,
        namespace=team_context.name,
        name=f"{team_context.name}-{plugin_id}",
        chart_name=chart_name,
        chart_version=chart_version,
    )


@hooks.destroy
def destroy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug(
        "Delete Plugin %s of Team Env name: %s | Team name: %s",
        plugin_id,
        context.name,
        team_context.name,
    )
    helm.uninstall_chart(f"{team_context.name}-{plugin_id}", namespace=team_context.name)
