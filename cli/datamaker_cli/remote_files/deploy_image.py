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
from typing import Optional, Tuple

from datamaker_cli import docker, plugins, sh
from datamaker_cli.manifest import Manifest
from datamaker_cli.remote_files import env, teams

_logger: logging.Logger = logging.getLogger(__name__)


def deploy_image(filename: str, args: Tuple[str, ...]) -> None:
    manifest: Manifest = Manifest(filename=filename)
    manifest.fetch_ssm()
    _logger.debug("manifest.name: %s", manifest.name)
    _logger.debug("args: %s", args)
    if len(args) == 1:
        image_name: str = args[1]
        script: Optional[str] = None
    elif len(args) == 2:
        image_name = args[1]
        script = args[2]
    else:
        raise ValueError("Unexpected number of values in args.")

    plugins.PLUGINS_REGISTRIES.load_plugins(manifest=manifest)
    _logger.debug("Plugins loaded")
    env.deploy(
        manifest=manifest,
        add_images=[image_name],
        remove_images=[],
    )
    _logger.debug("Env changes deployed")
    teams.deploy(manifest=manifest)
    _logger.debug("Teams Stacks deployed")

    path = os.path.join(manifest.filename_dir, image_name)
    _logger.debug("path: %s", path)
    _logger.debug("Deploying the %s Docker image", image_name)
    if manifest.images.get(image_name, {"source": "code"}).get("source") == "code":
        if script is not None:
            sh.run(f"sh {script}", cwd=path)
        docker.deploy_dynamic_image(manifest=manifest, dir=path, name=f"datamaker-{manifest.name}-{image_name}")
    else:
        docker.deploy(
            manifest=manifest, dir=path, image_name=image_name, deployed_name=f"datamaker-{manifest.name}-{image_name}"
        )
    _logger.debug("Docker Image Deployed to ECR")
