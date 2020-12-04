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

_logger: logging.Logger = logging.getLogger("datamaker_cli")


@hooks.deploy
def deploy(manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]) -> None:
    _logger.debug("Running hello_world deploy!")
    sh.run(f"echo 'Team Env name: {manifest.name}'")
    sh.run(f"echo 'Team name: {team_manifest.name}'")
    sh.run(f"echo 'Parameters keys: {list(parameters.keys())}'")


@hooks.destroy
def destroy(manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]) -> None:
    _logger.debug("Running hello_world destroy!")
    sh.run(f"echo 'Team Env name: {manifest.name}'")
    sh.run(f"echo 'Team name: {team_manifest.name}'")
    sh.run(f"echo 'Parameters keys: {list(parameters.keys())}'")


@hooks.dockerfile_injection
def dockerfile_injection(manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]) -> List[str]:
    _logger.debug("Team Env: %s | Team: %s | Image: %s", manifest.name, team_manifest.name, team_manifest.image)
    return ["RUN echo 'Hello World!' > /home/jovyan/hello-world-plugin.txt"]


@hooks.bootstrap_injection
def bootstrap_injection(manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]) -> str:
    _logger.debug("Injecting CodeCommit plugin commands for team %s Bootstrap", team_manifest.name)
    return """
#!/usr/bin/env bash
set -ex

echo 'Hello World 2!' > /home/jovyan/hello-world-plugin-2.txt

"""
