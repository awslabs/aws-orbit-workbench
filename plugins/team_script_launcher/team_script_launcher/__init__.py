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
from typing import Any, Dict, List

from datamaker_cli import sh
from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.plugins import hooks
from datamaker_cli import docker
from datamaker_cli.remote_files.utils import get_k8s_context
_logger: logging.Logger = logging.getLogger("datamaker_cli")
import os

PLUGIN_ID = 'team-script-launcher'
CONFIGMAP_SCRIPT_NAME = f'{PLUGIN_ID}-script'
POD_FILENAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'job_definition.yaml')

@hooks.deploy
def deploy(manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", manifest.name, team_manifest.name)
    sh.run(f"echo 'Team Env name: {manifest.name} | Team name: {team_manifest.name}'")
    # Run the following command to authorize calls to kubectl for the current client
    sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")

    if 'script' in parameters:
        scriptBody = parameters['script']
    else:
        raise Exception(f"Plugin {PLUGIN_ID} must define parameter 'script'")
    scriptFile = os.path.join(os.path.dirname(POD_FILENAME), f'{PLUGIN_ID}-script.sh')

    with open(scriptFile, "w") as file:
        file.write(scriptBody)

    # Cleanup of previous installation if needed
    sh.run(f"kubectl delete jobs/team-script-{PLUGIN_ID} --namespace {team_manifest.name} --ignore-not-found")
    sh.run(f"kubectl delete configmap {CONFIGMAP_SCRIPT_NAME} --namespace {team_manifest.name} --ignore-not-found")

    # Create the configmap with the script
    sh.run(f"kubectl create configmap {CONFIGMAP_SCRIPT_NAME} --from-file={scriptFile} --namespace {team_manifest.name}")
    _logger.debug(f"Create config map: {CONFIGMAP_SCRIPT_NAME} at namespace {team_manifest.name}" )

    context = get_k8s_context(manifest=manifest)
    _logger.debug("Using S3 Sync Pod at %s for Env name: %s | Team name: %s, CONTEXT: %s", POD_FILENAME, manifest.name, team_manifest.name, context)
    input = POD_FILENAME
    output = os.path.join(os.path.dirname(POD_FILENAME), f'{PLUGIN_ID}-team.yaml')

    with open(input, "r") as file:
        content: str = file.read()

    restartPolicy = parameters['restartPolicy'] if 'restartPolicy' in parameters else 'Never'
    content = content.replace("$", "").format(
        team=team_manifest.name,
        region=manifest.region,
        account_id=manifest.account_id,
        env_name=manifest.name,
        tag=team_manifest.manifest.images["jupyter-hub"]["version"],
        restartPolicy=restartPolicy,
        plugin_id=PLUGIN_ID
    )

    _logger.debug("Kubectl Team %s manifest:\n%s", team_manifest.name, content)
    with open(output, "w") as file:
        file.write(content)

    # run the POD to execute the script
    cmd = f"kubectl apply -f {output} --context {context} --namespace {team_manifest.name}"
    _logger.debug(cmd)
    sh.run(cmd)

@hooks.destroy
def destroy(manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]) -> None:
    _logger.debug("Delete Plugin %s of Team Env name: %s | Team name: %s",PLUGIN_ID, manifest.name, team_manifest.name)
    sh.run(f"echo 'Team Env name: {manifest.name} | Team name: {team_manifest.name}'")
    sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")

    sh.run(f"kubectl delete jobs/team-script-{PLUGIN_ID} --namespace {team_manifest.name} --ignore-not-found")
    sh.run(f"kubectl delete configmap {CONFIGMAP_SCRIPT_NAME} --namespace {team_manifest.name} --ignore-not-found")
