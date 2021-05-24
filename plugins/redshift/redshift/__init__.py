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
import time
from typing import TYPE_CHECKING, Any, Dict

import boto3
from aws_orbit import sh
from aws_orbit.plugins import hooks
from aws_orbit.plugins.helpers import cdk_deploy, cdk_destroy

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger("aws_orbit")

PLUGIN_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))


@hooks.deploy
def deploy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug("Deploying Redshift plugin resources for team %s", team_context.name)
    sh.run(f"echo 'Team name: {team_context.name} | Plugin ID: {plugin_id}'")
    cdk_deploy(
        stack_name=f"orbit-{context.name}-{team_context.name}-{plugin_id}-redshift",
        app_filename=os.path.join(PLUGIN_ROOT_PATH, "orbit_redshift_stack.py"),
        context=context,
        team_context=team_context,
        parameters=parameters,
    )


@hooks.destroy
def destroy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug("Destroying Redshift plugin resources for team %s", team_context.name)
    sh.run(f"echo 'Team name: {team_context.name} | Plugin ID: {plugin_id}'")
    # Delete left over redshift cluster(s) before deleting plugin resources
    try:
        pass
        redshift = boto3.client("redshift")
        clusters = redshift.describe_clusters(TagValues=[team_context.name])["Clusters"]
        namespace = "orbit-" + context.name + "-" + team_context.name + "-"
        # Deleting redshift clusters in parallel.
        for cluster in clusters:
            cluster_id = cluster["ClusterIdentifier"]
            _logger.debug(f"cluster_id={cluster_id}")
            cluster_name = cluster_id if namespace in cluster_id else namespace + cluster_id
            redshift.delete_cluster(ClusterIdentifier=cluster_name, SkipFinalClusterSnapshot=True)
            _logger.debug(f"Delete redshift cluster_name={cluster_name}")
        # Hold before destroying the redshift plugin resource.
        time.sleep(180)
        _logger.debug(f"Deleted {team_context.name} team redshift clusters")
    except Exception as e:
        _logger.error("Error deleting team %s redshift cluster(s) : %s", team_context.name, e)
        raise e

    cdk_destroy(
        stack_name=f"orbit-{context.name}-{team_context.name}-{plugin_id}-redshift",
        app_filename=os.path.join(PLUGIN_ROOT_PATH, "orbit_redshift_stack.py"),
        context=context,
        team_context=team_context,
        parameters=parameters,
    )
