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
from typing import List

from datamaker_cli import cdk
from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.plugins import hooks

_logger: logging.Logger = logging.getLogger("datamaker_cli")

DATAMAKER_CODE_COMMIT_ROOT = os.path.dirname(os.path.abspath(__file__))


@hooks.deploy.team
def deploy_team(manifest: Manifest, team_manifest: TeamManifest) -> None:
    _logger.debug("Deploying CodeCommit plugin resources for team %s", team_manifest.name)
    cdk.deploy(
        manifest=manifest,
        stack_name=f"datamaker-{manifest.name}-{team_manifest.name}-codecommit",
        app_filename=os.path.join(DATAMAKER_CODE_COMMIT_ROOT, "cdk.py"),
        args=[manifest.filename, team_manifest.name],
    )


@hooks.destroy.team
def destroy_team(manifest: Manifest, team_manifest: TeamManifest) -> None:
    _logger.debug("Destroying CodeCommit plugin resources for team %s", team_manifest.name)
    cdk.destroy(
        manifest=manifest,
        stack_name=f"datamaker-{manifest.name}-{team_manifest.name}-codecommit",
        app_filename=os.path.join(DATAMAKER_CODE_COMMIT_ROOT, "cdk.py"),
        args=[manifest.filename, team_manifest.name],
    )


@hooks.images.dockerfile_injection
def dockerfile_injection(manifest: Manifest, team_manifest: TeamManifest) -> List[str]:
    _logger.debug("Injecting CodeCommit plugin commands for team %s Image", team_manifest.name)
    return [
        "RUN pip install --upgrade jupyterlab-git",
        "RUN jupyter lab build",
    ]


@hooks.images.bootstrap_injection
def bootstrap_injection(manifest: Manifest, team_manifest: TeamManifest) -> str:
    _logger.debug("Injecting CodeCommit plugin commands for team %s Bootstrap", team_manifest.name)
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
REPO_ADDRESS="https://git-codecommit.${AWS_DEFAULT_REGION}.amazonaws.com/v1/repos/datamaker-${AWS_DATAMAKER_ENV}-${DATAMAKER_TEAM_SPACE}"

if [ ! -d "${REPO_LOCAL_PATH}" ] ; then
    git clone "${REPO_ADDRESS}" "${REPO_LOCAL_PATH}"
fi
chown -R jovyan "${REPO_LOCAL_PATH}"

"""
