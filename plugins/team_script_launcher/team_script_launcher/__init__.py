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
from typing import Any, Dict

from datamaker_cli import sh
from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.plugins import hooks

_logger: logging.Logger = logging.getLogger("datamaker_cli")
POD_FILENAME = os.path.join(os.path.dirname(__file__), "job_definition.yaml")


@hooks.deploy
def deploy(plugin_id: str, manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", manifest.name, team_manifest.name)
    configmap_script_name = f"{plugin_id}-script"

    if "script" in parameters:
        script_body = parameters["script"]
    else:
        raise Exception(f"Plugin {plugin_id} must define parameter 'script'")
    script_file = os.path.join(os.path.dirname(POD_FILENAME), f"{plugin_id}-script.sh")

    with open(script_file, "w") as file:
        file.write(script_body)

    # Cleanup of previous installation if needed
    sh.run(f"kubectl delete jobs/team-script-{plugin_id} --namespace {team_manifest.name} --ignore-not-found")
    sh.run(f"kubectl delete configmap {configmap_script_name} --namespace {team_manifest.name} --ignore-not-found")

    # Create the configmap with the script
    sh.run(
        f"kubectl create configmap {configmap_script_name} --from-file={script_file} --namespace {team_manifest.name}"
    )
    _logger.debug(f"Create config map: {configmap_script_name} at namespace {team_manifest.name}")

    _logger.debug(
        "Using S3 Sync Pod at %s for Env name: %s | Team name: %s",
        POD_FILENAME,
        manifest.name,
        team_manifest.name,
    )
    input = POD_FILENAME
    output = os.path.join(os.path.dirname(POD_FILENAME), f"{plugin_id}-team.yaml")

    with open(input, "r") as file:
        content: str = file.read()

    restart_policy = parameters["restartPolicy"] if "restartPolicy" in parameters else "Never"
    content = content.replace("$", "").format(
        team=team_manifest.name,
        region=manifest.region,
        account_id=manifest.account_id,
        env_name=manifest.name,
        tag=team_manifest.manifest.images["jupyter-hub"]["version"],
        restart_policy=restart_policy,
        plugin_id=plugin_id,
    )

    _logger.debug("Kubectl Team %s manifest:\n%s", team_manifest.name, content)
    with open(output, "w") as file:
        file.write(content)

    # run the POD to execute the script
    cmd = f"kubectl apply -f {output}  --namespace {team_manifest.name}"
    _logger.debug(cmd)
    sh.run(cmd)


@hooks.destroy
def destroy(plugin_id: str, manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]) -> None:
    _logger.debug("Delete Plugin %s of Team Env name: %s | Team name: %s", plugin_id, manifest.name, team_manifest.name)
    sh.run(f"kubectl delete jobs/team-script-{plugin_id} --namespace {team_manifest.name} --ignore-not-found")
    sh.run(f"kubectl delete configmap {plugin_id}-script --namespace {team_manifest.name} --ignore-not-found")
