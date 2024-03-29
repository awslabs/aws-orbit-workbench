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
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, cast

import aws_orbit
from aws_orbit import exceptions, sh, utils
from aws_orbit.plugins import hooks
from aws_orbit.remote_files import helm
from aws_orbit.services import s3

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext
_logger: logging.Logger = logging.getLogger("aws_orbit")
CHART_PATH = os.path.join(os.path.dirname(__file__), "charts")


def helm_package(
    plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]
) -> Tuple[str, str, str]:
    chart_path = helm.create_team_charts_copy(team_context=team_context, path=CHART_PATH, target_path=plugin_id)
    _logger.debug("copy chart dir")
    utils.print_dir(chart_path)
    if "image" not in parameters:
        image = f"{context.images.jupyter_user.repository}:{context.images.jupyter_user.version}"
    elif "aws-orbit-workbench/utility-data" in parameters["image"]:
        image = f"{context.images.utility_data.repository}:{context.images.utility_data.version}"
    else:
        image = parameters["image"]

    _logger.debug(f"For plugin {plugin_id} using image: {image}")

    vars: Dict[str, Optional[str]] = dict(
        team=team_context.name,
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        tag=parameters["tag"] if "tag" in parameters else context.images.jupyter_user.version,
        restart_policy=parameters["restartPolicy"] if "restartPolicy" in parameters else "Never",
        plugin_id=plugin_id,
        toolkit_s3_bucket=context.toolkit.s3_bucket,
        image_pull_policy="Always" if aws_orbit.__version__.endswith(".dev0") else "IfNotPresent",
        image=image,
        uid=parameters["uid"] if "uid" in parameters else "1000",
        gid=parameters["gid"] if "gid" in parameters else "100",
    )

    if "script" in parameters:
        script_body = parameters["script"]
    else:
        raise Exception(f"Plugin {plugin_id} must define parameter 'script'")
    script_file = os.path.join(chart_path, "team-script-launcher", "script.txt")

    script_body = utils.resolve_parameters(script_body, vars)
    with open(script_file, "w") as file:
        file.write(script_body)

    if not team_context.team_helm_repository:
        raise Exception("Missing team helm repository")

    repo_location = team_context.team_helm_repository
    repo = team_context.name
    _logger.debug(script_body)
    _init_team_repo(context=context, team_context=team_context, repo_location=repo_location)
    helm.add_repo(repo=repo, repo_location=repo_location)
    chart_name, chart_version, chart_package = helm.package_chart(
        repo=repo, chart_path=os.path.join(chart_path, "team-script-launcher"), values=vars
    )
    return (chart_name, chart_version, chart_package)


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
    if parameters.get("scope", "deploy") == "deploy":
        repo = team_context.name
        chart_name, chart_version, chart_package = helm_package(plugin_id, context, team_context, parameters)

        release_name = f"{team_context.name}-{plugin_id}".replace("_", "-")
        if helm.is_exists_chart_release(release_name, team_context.name):
            helm.uninstall_chart(release_name, team_context.name)
            time.sleep(60)

        helm.install_chart_no_upgrade(
            repo=repo,
            namespace=team_context.name,
            name=release_name,
            chart_name=chart_name,
            chart_version=chart_version,
        )
    else:
        _logger.debug("Skipping plugin deploy hook")


@hooks.destroy
def destroy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug(
        "Delete Plugin %s of Team Env name: %s | Team name: %s",
        plugin_id,
        context.name,
        team_context.name,
    )
    release_name = f"{team_context.name}-{plugin_id}".replace("_", "-")

    if "scope" in parameters and parameters["scope"] == "destroy":
        # Create new chart, release and respective job
        repo = team_context.name
        chart_name, chart_version, chart_package = helm_package(plugin_id, context, team_context, parameters)

        if helm.is_exists_chart_release(release_name, team_context.name):
            helm.uninstall_chart(release_name, team_context.name)
            time.sleep(60)

        if ns_exists(team_context=team_context):
            helm.install_chart_no_upgrade(
                repo=repo,
                namespace=team_context.name,
                name=release_name,
                chart_name=chart_name,
                chart_version=chart_version,
            )
            # wait for job completion
            try:
                sh.run(
                    f"kubectl wait --for=condition=complete "
                    f"--timeout=120s job/{plugin_id} --namespace {team_context.name}"
                )
            except Exception as e:
                _logger.error(e)

        # destroy
        helm.uninstall_chart(release_name, namespace=team_context.name)
        return

    # For Deploy Scope
    helm.uninstall_chart(release_name, namespace=team_context.name)


def _init_team_repo(context: "Context", team_context: "TeamContext", repo_location: str) -> None:
    if not s3.object_exists(
        bucket=cast(str, context.toolkit.s3_bucket), key=f"helm/repositories/teams/{team_context.name}/index.yaml"
    ):
        _logger.debug("Initializing Team Helm Respository at %s", repo_location)
        sh.run(f"helm s3 init {repo_location}")
    else:
        _logger.debug("Skipping initialization of existing Team Helm Repository at %s", repo_location)


def ns_exists(team_context: "TeamContext") -> bool:
    namespace = team_context.name
    try:
        _logger.info(f"Checking if {namespace} exists")
        found = False
        for line in sh.run_iterating("kubectl get ns"):
            _logger.info(line)
            if namespace in line:
                found = True

        return found
    except exceptions.FailedShellCommand as e:
        _logger.error(e)
        raise e
