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
from typing import TYPE_CHECKING, List, Optional, Tuple, cast

from boto3 import client

from aws_orbit import docker, plugins, sh
from aws_orbit.models.context import load_context_from_ssm
from aws_orbit.remote_files import teams as team_utils
from aws_orbit.utils import boto3_client

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext
    from aws_orbit.models.manifest import ImageManifest

_logger: logging.Logger = logging.getLogger(__name__)


def build_image(args: Tuple[str, ...]) -> None:
    if len(args) < 4:
        raise ValueError("Unexpected number of values in args.")
    env: str = args[0]
    image_name: str = args[1]
    script: Optional[str] = args[2] if args[2] != "NO_SCRIPT" else None
    teams: Optional[List[str]] = list(set(args[3].split(","))) if args[3] != "NO_TEAMS" else None
    build_args = args[4:]

    _logger.debug("args: %s", args)
    context: "Context" = load_context_from_ssm(env_name=env)

    plugins.PLUGINS_REGISTRIES.load_plugins(context=context, plugin_changesets=[], teams_changeset=None)
    _logger.debug("Plugins loaded")

    docker.login(context=context)
    _logger.debug("DockerHub and ECR Logged in")

    ecr = boto3_client("ecr")
    ecr_repo = f"orbit-{context.name}-{image_name}"
    try:
        ecr.describe_repositories(repositoryNames=[ecr_repo])
    except ecr.exceptions.RepositoryNotFoundException:
        _create_repository(context.name, ecr, ecr_repo)

    image_def: Optional["ImageManifest"] = getattr(context.images, image_name, None)
    _logger.debug("image def: %s", image_def)

    if image_def is None or getattr(context.images, image_name).source == "code":
        path = image_name
        _logger.debug("path: %s", path)
        if script is not None:
            sh.run(f"sh {script}", cwd=path)
        docker.deploy_image_from_source(
            context=context, dir=path, name=ecr_repo, build_args=cast(Optional[List[str]], build_args)
        )
    else:
        docker.replicate_image(context=context, image_name=image_name, deployed_name=ecr_repo)
    _logger.debug("Docker Image Deployed to ECR")

    if teams:
        _logger.debug(f"Building and Deploying Team images: {teams}")
        for team_name in teams:
            team_context: Optional["TeamContext"] = context.get_team_by_name(name=team_name)
            if team_context:
                team_utils._deploy_team_image(context=context, team_context=team_context, image=image_name)
            else:
                _logger.debug(f"Skipped unknown Team: {team_name}")


def _create_repository(env_name: str, ecr: client, ecr_repo: str) -> None:
    response = ecr.create_repository(
        repositoryName=ecr_repo,
        tags=[
            {"Key": "Env", "Value": env_name},
        ],
    )
    if "repository" in response and "repositoryName" in response["repository"]:
        _logger.debug("ECR repository not exist, creating for %s", ecr_repo)
    else:
        _logger.error("ECR repository creation failed, response %s", response)
        raise RuntimeError(response)
