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
from typing import Optional, Tuple

from boto3 import client

from aws_orbit import changeset, docker, plugins, sh
from aws_orbit.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def build_image(args: Tuple[str, ...]) -> None:
    env: str
    image_name: str
    script: Optional[str]
    if len(args) == 2:
        env = args[0]
        image_name = args[1]
        script = None
    elif len(args) == 3:
        env = args[0]
        image_name = args[1]
        script = args[2]
    else:
        raise ValueError("Unexpected number of values in args.")

    _logger.debug("args: %s", args)

    manifest: Manifest = Manifest(filename=None, env=env, region=None)
    manifest.fillup()
    # if manifest.demo:
    #     manifest.fetch_demo_data()
    #     manifest.fetch_network_data()

    docker.login(manifest=manifest)
    _logger.debug("DockerHub and ECR Logged in")

    changes: changeset.Changeset = changeset.read_changeset_file(manifest=manifest, filename="changeset.json")
    _logger.debug(f"Changeset: {changes.asdict()}")
    _logger.debug("Changeset loaded")

    plugins.PLUGINS_REGISTRIES.load_plugins(
        manifest=manifest, plugin_changesets=changes.plugin_changesets, teams_changeset=changes.teams_changeset
    )
    _logger.debug("Plugins loaded")
    ecr = manifest.boto3_client("ecr")
    ecr_repo = f"orbit-{manifest.name}-{image_name}"
    try:
        ecr.describe_repositories(repositoryNames=[ecr_repo])
    except ecr.exceptions.RepositoryNotFoundException:
        _create_repository(manifest, ecr, ecr_repo)
    image_def = manifest.images.get(image_name)
    _logger.debug(" image def: %s", image_def)
    if manifest.images.get(image_name, {"source": "code"}).get("source") == "code":
        path = image_name
        _logger.debug("path: %s", path)
        if script is not None:
            sh.run(f"sh {script}", cwd=path)
        docker.deploy_image_from_source(manifest=manifest, dir=path, name=ecr_repo)
    else:
        docker.replicate_image(manifest=manifest, image_name=image_name, deployed_name=ecr_repo)
    _logger.debug("Docker Image Deployed to ECR")


def _create_repository(manifest: Manifest, ecr: client, ecr_repo: str) -> None:
    response = ecr.create_repository(
        repositoryName=ecr_repo,
        tags=[
            {"Key": "Env", "Value": manifest.name},
        ],
    )
    if "repository" in response and "repositoryName" in response["repository"]:
        _logger.debug("ECR repository not exist, creating for %s", ecr_repo)
    else:
        _logger.error("ECR repository creation failed, response %s", response)
        raise RuntimeError(response)
