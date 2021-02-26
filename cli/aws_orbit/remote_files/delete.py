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

from aws_orbit.models.context import ContextSerDe
from aws_orbit.remote_files import env
from aws_orbit.services import ecr

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def delete_image(args: Tuple[str, ...]) -> None:
    _logger.debug("args %s", args)
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=args[0], type=Context)
    _logger.debug("context.name %s", context.name)
    if len(args) == 2:
        image_name: str = args[1]
    else:
        raise ValueError("Unexpected number of values in args.")

    env.deploy(context=context, add_images=[], remove_images=[image_name], eks_system_masters_roles_changes=None)
    _logger.debug("Env changes deployed")
    ecr.delete_repo(repo=f"orbit-{context.name}-{image_name}")
    _logger.debug("Docker Image Destroyed from ECR")
