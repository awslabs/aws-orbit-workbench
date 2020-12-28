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

from aws_orbit.manifest import Manifest
from aws_orbit.remote_files import env
from aws_orbit.services import ecr

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
    ecr.delete_repo(manifest=manifest, repo=f"orbit-{manifest.name}-{image_name}")
    _logger.debug("Docker Image Destroyed from ECR")
