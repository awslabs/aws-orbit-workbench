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
from typing import TYPE_CHECKING, Any, Dict, List

from aws_orbit.plugins import hooks
from aws_orbit.plugins.helpers import cdk_deploy, cdk_destroy

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger("aws_orbit")

ORBIT_CODE_COMMIT_ROOT = os.path.dirname(os.path.abspath(__file__))


@hooks.deploy
def deploy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug("Deploying CodeCommit plugin resources for team %s", team_context.name)
    cdk_deploy(
        stack_name=f"orbit-{context.name}-{team_context.name}-codecommit",
        app_filename=os.path.join(ORBIT_CODE_COMMIT_ROOT, "cdk.py"),
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
    _logger.debug("Destroying CodeCommit plugin resources for team %s", team_context.name)
    cdk_destroy(
        stack_name=f"orbit-{context.name}-{team_context.name}-codecommit",
        app_filename=os.path.join(ORBIT_CODE_COMMIT_ROOT, "cdk.py"),
        context=context,
        team_context=team_context,
        parameters=parameters,
    )


@hooks.dockerfile_injection
def dockerfile_injection(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> List[str]:
    _logger.debug("Injecting CodeCommit plugin commands for team %s Image", team_context.name)
    return [
        "RUN pip install --upgrade jupyterlab-git",
        "RUN jupyter lab build --dev-build=False -y ",
        "RUN jupyter lab clean -y",
        "RUN npm cache clean --force",
    ]


@hooks.bootstrap_injection
def bootstrap_injection(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> str:
    _logger.debug("Injecting CodeCommit plugin commands for team %s Bootstrap", team_context.name)
    return """
#!/usr/bin/env bash
set -ex

configs='
[credential]
        helper = !aws codecommit credential-helper $@
        UseHttpPath = true
[core]
        editor = /usr/bin/nano
'

echo "$configs" > /home/jovyan/.gitconfig

REPO_LOCAL_PATH="/efs/"${USERNAME}"/codecommit"
REPO_ADDRESS="https://git-codecommit.${AWS_DEFAULT_REGION}.amazonaws.com/v1/repos/orbit-${AWS_ORBIT_ENV}-${AWS_ORBIT_TEAM_SPACE}"

if [ ! -d "${REPO_LOCAL_PATH}" ] ; then
    git clone "${REPO_ADDRESS}" "${REPO_LOCAL_PATH}"
fi
chown -R jovyan "${REPO_LOCAL_PATH}"

"""
