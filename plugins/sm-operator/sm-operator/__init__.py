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
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from aws_orbit import sh, utils
from aws_orbit.plugins import hooks
from aws_orbit.remote_files import helm


if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext
_logger: logging.Logger = logging.getLogger("aws_orbit")
CHART_PATHS = os.path.join(os.path.dirname(__file__))

@hooks.deploy
def deploy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    release_name = f"{team_context.name}-{plugin_id}"

    ### Logic
    # If there is a CRD that needs to be installed:
    #  1. Check if the plugin is installed
    #     a. YES - then you can run 'helm update --install' via helm.install_chart_no_upgrade and the chart will install 
    #        but the CRD's will not (they are global and immutable)
    #     b. NO - install the chart and the crd - 'helm install' via via helm.install_chart
    #  2. CRD's are global
    # REF: https://helm.sh/docs/topics/charts/
    ###


    _logger.info("Checking Chart %s is installed...", release_name)
    fresh_install = True
    if helm.is_exists_chart_release(release_name, team_context.name):
        _logger.info("Chart %s already installed, removing to begin new install", release_name)
        fresh_install = True


    vars: Dict[str, Optional[str]] = dict(
        team=team_context.name,
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        plugin_id=plugin_id,
        roleArn = team_context.eks_pod_role_arn
    )


    chart_path = helm.create_team_charts_copy(team_context=team_context, path=CHART_PATHS)
    _logger.debug("package dir")
    utils.print_dir(CHART_PATHS)
    _logger.debug("copy chart dir")
    utils.print_dir(chart_path)

    repo_location = helm.init_team_repo(context=context, team_context=team_context)
    repo = team_context.name
    helm.add_repo(repo=repo, repo_location=repo_location)
    chart_name, chart_version, chart_package = helm.package_chart(
        repo=repo, chart_path=chart_path, values=vars
    )
   
    if fresh_install:
        _logger.info("Chart %s already installed, calling for update ", release_name)
        helm.install_chart(
            repo=repo,
            namespace=team_context.name,
            name=release_name,
            chart_name=chart_name,
            chart_version=chart_version,
        )
    else:
        _logger.info("Chart %s not installed, calling for full install  ", release_name)
        helm.install_chart_no_upgrade(   
            repo=repo,
            namespace=team_context.name,
            name=release_name,
            chart_name=chart_name,
            chart_version=chart_version,
        )

    chart_name, chart_version, chart_package = helm.package_chart(
        repo=repo, chart_path=chart_path, values=vars
    )
    _logger.info(f"Sagemaker Operator Helm Chart {chart_name}@{chart_version} installed for {team_context.name} at {chart_package}")


@hooks.destroy
def destroy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Delete Plugin %s of Team Env name: %s | Team name: %s", plugin_id, context.name, team_context.name)
    helm.uninstall_chart_in_namespace(f"{team_context.name}-{plugin_id}",team_context.name)
