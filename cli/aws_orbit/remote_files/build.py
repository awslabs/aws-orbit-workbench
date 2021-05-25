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
from typing import List, Optional, Tuple, cast

from aws_orbit import docker, sh
from aws_orbit.models.context import Context, ContextSerDe
from aws_orbit.models.manifest import ImageManifest
from aws_orbit.services import ecr

_logger: logging.Logger = logging.getLogger(__name__)


def build_image(args: Tuple[str, ...]) -> None:
    if len(args) < 4:
        raise ValueError("Unexpected number of values in args.")
    env: str = args[0]
    image_name: str = args[1]
    script: Optional[str] = args[2] if args[2] != "NO_SCRIPT" else None
    source_registry: Optional[str]
    if args[3] != "NO_REPO":
        if len(args) < 6:
            raise Exception("Source registry is defined without 'source_repository' or 'source_version' ")
        source_registry = args[3]
        source_repository: str = args[4]
        source_version: str = args[5]
        build_args = args[6:]
        _logger.info("replicating image %s: %s %s:%s", image_name, source_registry, source_repository, source_version)
    else:
        _logger.info("building image %s: %s", image_name, script)
        build_args = args[4:]
        source_registry = None
    _logger.debug("args: %s", args)
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)

    docker.login(context=context)
    _logger.debug("DockerHub and ECR Logged in")

    ecr_repo = (
        f"orbit-{context.name}/{image_name}"
        if image_name in [n.replace("_", "-") for n in context.images.names]
        else f"orbit-{context.name}/users/{image_name}"
    )
    if not ecr.describe_repositories(repository_names=[ecr_repo]):
        ecr.create_repository(repository_name=ecr_repo, env_name=context.name)

    image_def: Optional["ImageManifest"] = getattr(context.images, image_name.replace("-", "_"), None)
    _logger.debug("image def: %s", image_def)

    if source_registry:
        docker.replicate_image(
            context=context,
            image_name=image_name,
            deployed_name=ecr_repo,
            source=source_registry,
            source_repository=source_repository,
            source_version=source_version,
        )
    elif image_def is None or image_def.get_source(account_id=context.account_id, region=context.region) == "code":
        path = os.path.join(os.getcwd(), image_name)
        if not os.path.exists(path):
            bundle_dir = os.path.join(os.getcwd(), "bundle", image_name)
            if os.path.exists(bundle_dir):
                path = bundle_dir
            else:
                raise RuntimeError(f"Unable to locate source in {path} or {bundle_dir}")

        _logger.debug("path: %s", path)
        if script is not None:
            sh.run(f"sh {script}", cwd=path)
        tag = cast(str, image_def.version if image_def else "latest")
        docker.deploy_image_from_source(
            context=context, dir=path, name=ecr_repo, tag=tag, build_args=cast(Optional[List[str]], build_args)
        )
    else:
        docker.replicate_image(context=context, image_name=image_name, deployed_name=ecr_repo)
    _logger.debug("Docker Image Deployed to ECR")
