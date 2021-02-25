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
from typing import TYPE_CHECKING, Tuple

from aws_orbit import plugins
from aws_orbit.models.context import load_context_from_ssm
from aws_orbit.remote_files import cdk_toolkit, demo, eksctl, env, kubectl, teams
from aws_orbit.services import ecr, ssm

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def delete_image(args: Tuple[str, ...]) -> None:
    _logger.debug("args %s", args)
    env_name: str = args[0]
    context: "Context" = load_context_from_ssm(env_name=env_name)

    if len(args) == 2:
        image_name: str = args[1]
    else:
        raise ValueError("Unexpected number of values in args.")

    env.deploy(context=context, add_images=[], remove_images=[image_name], eks_system_masters_roles_changes=None)
    _logger.debug("Env changes deployed")
    ecr.delete_repo(repo=f"orbit-{context.name}-{image_name}")
    _logger.debug("Docker Image Destroyed from ECR")


def destroy(args: Tuple[str, ...]) -> None:
    _logger.debug("args %s", args)
    env_name: str = args[0]
    context: "Context" = load_context_from_ssm(env_name=env_name)
    _logger.debug("context.name %s", context.name)

    if len(args) == 2:
        teams_only: bool = args[1] == "teams-stacks"
        keep_demo: bool = args[1] == "keep-demo"
    else:
        raise ValueError("Unexpected number of values in args.")

    plugins.PLUGINS_REGISTRIES.load_plugins(context=context, plugin_changesets=[], teams_changeset=None)
    _logger.debug("Plugins loaded")

    kubectl.destroy_teams(context=context)
    _logger.debug("Kubernetes Team components destroyed")
    eksctl.destroy_teams(context=context)
    _logger.debug("EKS Team Stacks destroyed")
    teams.destroy_all(context=context)
    _logger.debug("Teams Stacks destroyed")
    ssm.cleanup_teams(env_name=context.name)

    if not teams_only:
        kubectl.destroy_env(context=context)
        _logger.debug("Kubernetes Environment components destroyed")
        eksctl.destroy_env(context=context)
        _logger.debug("EKS Environment Stacks destroyed")
        env.destroy(context=context)
        _logger.debug("Env Stack destroyed")
        if not keep_demo:
            demo.destroy(context=context)
            _logger.debug("Demo Stack destroyed")
            cdk_toolkit.destroy(context=context)
            _logger.debug("CDK Toolkit Stack destroyed")
    else:
        _logger.debug("Skipping Environment, Demo, and CDK Toolkit Stacks")
