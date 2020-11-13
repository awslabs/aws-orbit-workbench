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
from typing import Tuple

from datamaker_cli import plugins
from datamaker_cli.manifest import Manifest
from datamaker_cli.remote_files import cdk_toolkit, demo, eksctl, env, kubectl, teams
from datamaker_cli.services import ecr

_logger: logging.Logger = logging.getLogger(__name__)


def destroy_image(filename: str, args: Tuple[str, ...]) -> None:
    manifest: Manifest = Manifest(filename=filename)
    _logger.debug("manifest.name %s", manifest.name)
    _logger.debug("args %s", args)
    if len(args) == 1:
        image_name: str = args[0]
    else:
        raise ValueError("Unexpected number of values in args.")

    env.deploy(manifest=manifest, add_images=[], remove_images=[image_name])
    _logger.debug("Env changes deployed")
    ecr.delete_repo(manifest=manifest, repo=f"datamaker-{manifest.name}-{image_name}")
    _logger.debug("Docker Image Destroyed from ECR")


def destroy(filename: str, args: Tuple[str, ...]) -> None:
    manifest: Manifest = Manifest(filename=filename)
    _logger.debug("manifest.name %s", manifest.name)
    _logger.debug("args %s", args)
    if len(args) == 0:
        teams_only = False
    elif len(args) == 1:
        teams_only = (args[0] == "teams-only")
    else:
        raise ValueError("Unexpected number of values in args.")

    manifest.fillup()
    plugins.load_plugins(manifest=manifest)
    _logger.debug(f"Plugins: {','.join([p.name for p in manifest.plugins])}")
    kubectl.destroy_teams(manifest=manifest)
    _logger.debug("Kubernetes Team components destroyed")
    eksctl.destroy_teams(manifest=manifest)
    _logger.debug("EKS Team Stacks destroyed")
    teams.destroy(manifest=manifest)
    _logger.debug("Teams Stacks destroyed")

    if not teams_only:
        kubectl.destroy_env(manifest=manifest)
        _logger.debug("Kubernetes Environment components destroyed")
        eksctl.destroy_env(manifest=manifest)
        _logger.debug("EKS Environment Stacks destroyed")
        env.destroy(manifest=manifest)
        _logger.debug("Env Stack destroyed")
        demo.destroy(manifest=manifest)
        _logger.debug("Demo Stack destroyed")
        cdk_toolkit.destroy(manifest=manifest)
        _logger.debug("CDK Toolkit Stack destroyed")
    else:
        _logger.debug("Skipping Environment, Demo, and CDK Toolkit Stacks")