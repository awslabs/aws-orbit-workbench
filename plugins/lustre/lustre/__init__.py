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
from aws_orbit.services import ec2
from aws_orbit.services.ec2 import IpPermission, UserIdGroupPair

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext
_logger: logging.Logger = logging.getLogger("aws_orbit")
CHARTS_PATH = os.path.join(os.path.dirname(__file__), "charts")


@hooks.deploy
def deploy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    release_name = f"{team_context.name}-{plugin_id}"
    _logger.info("Checking Chart %s is installed...", release_name)
    if helm.is_exists_chart_release(release_name, team_context.name):
        _logger.info("Chart %s already installed, skipping installation", release_name)
        return
    try:
        sh.run(f"kubectl delete sc fsx-lustre-{team_context.name}-fast-fs-lustre")
    except Exception as e:
        _logger.error(f"Deleting prior sc 'fsx-lustre-{team_context.name}-fast-fs-lustre' failed with:%s", str(e))

    vars: Dict[str, Optional[str]] = dict(
        team=team_context.name,
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        plugin_id=plugin_id,
        deploymentType="SCRATCH_2",
        sg=team_context.team_security_group_id,
        subnet=context.networking.data.nodes_subnets[0],
        s3importpath=f"s3://{team_context.scratch_bucket}/{team_context.name}/lustre",
        s3exportpath=f"s3://{team_context.scratch_bucket}/{team_context.name}/lustre",
    )

    ec2.authorize_security_group_ingress(
        group_id=cast(str, team_context.team_security_group_id),
        ip_permissions=[
            IpPermission(
                from_port=988,
                to_port=988,
                ip_protocol="tcp",
                user_id_group_pairs=[
                    UserIdGroupPair(description="All from Cluster", group_id=cast(str, context.cluster_sg_id))
                ],
            )
        ],
    )

    chart_path = helm.create_team_charts_copy(team_context=team_context, path=CHARTS_PATH)
    _logger.debug("package dir")
    utils.print_dir(CHARTS_PATH)
    _logger.debug("copy chart dir")
    utils.print_dir(chart_path)

    repo_location = helm.init_team_repo(context=context, team_context=team_context)
    repo = team_context.name
    helm.add_repo(repo=repo, repo_location=repo_location)
    chart_name, chart_version, chart_package = helm.package_chart(
        repo=repo, chart_path=os.path.join(chart_path, "fsx_storageclass"), values=vars
    )
    helm.install_chart_no_upgrade(
        repo=repo,
        namespace=team_context.name,
        name=release_name,
        chart_name=chart_name,
        chart_version=chart_version,
    )

    chart_name, chart_version, chart_package = helm.package_chart(
        repo=repo, chart_path=os.path.join(chart_path, "fsx_filesystem"), values=vars
    )
    _logger.info(f"Lustre Helm Chart {chart_name}@{chart_version} installed for {team_context.name} at {chart_package}")


@hooks.destroy
def destroy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Delete Plugin %s of Team Env name: %s | Team name: %s", plugin_id, context.name, team_context.name)
    helm.uninstall_chart(f"{team_context.name}-{plugin_id}")
