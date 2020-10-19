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

from datamaker_cli.manifest import Manifest, TeamManifest
from datamaker_cli.plugins import hooks
from datamaker_cli import sh

_logger: logging.Logger = logging.getLogger("datamaker_cli")


@hooks.deploy.demo
def deploy_demo(manifest: Manifest) -> None:
    _logger.debug("Env name: %s", manifest.name)
    sh.run(f"echo 'Env name: {manifest.name}'")


@hooks.deploy.env
def deploy_env(manifest: Manifest) -> None:
    _logger.debug("Env VPC: %s", manifest.vpc.vpc_id)
    sh.run(f"echo 'Env VPC: {manifest.vpc.vpc_id}'")


@hooks.deploy.team
def deploy_team(manifest: Manifest, team_manifest: TeamManifest) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", manifest.name, team_manifest.name)
    sh.run(f"echo 'Team Env name: {manifest.name} | Team name: {team_manifest.name}'")


@hooks.destroy.demo
def destroy_demo(manifest: Manifest) -> None:
    _logger.debug("Env name: %s", manifest.name)
    sh.run(f"echo 'Env name: {manifest.name}'")


@hooks.destroy.env
def destroy_env(manifest: Manifest) -> None:
    _logger.debug("Env VPC: %s", manifest.vpc.vpc_id)
    sh.run(f"echo 'Env VPC: {manifest.vpc.vpc_id}'")


@hooks.destroy.team
def destroy_team(manifest: Manifest, team_manifest: TeamManifest) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", manifest.name, team_manifest.name)
    sh.run(f"echo 'Team Env name: {manifest.name} | Team name: {team_manifest.name}'")
