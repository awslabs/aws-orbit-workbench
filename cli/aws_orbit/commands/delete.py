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

from aws_orbit.messages import MessagesContext
from aws_orbit.models.context import Context, ContextSerDe
from aws_orbit.remote_files import delete
from aws_orbit.services import cfn, ssm

_logger: logging.Logger = logging.getLogger(__name__)


def delete_image(env: str, name: str, debug: bool) -> None:
    with MessagesContext("Destroying Docker Image", debug=debug) as msg_ctx:
        if not name:
            raise ValueError("Image name required to delete")

        ssm.cleanup_changeset(env_name=env)
        ssm.cleanup_manifest(env_name=env)
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
        msg_ctx.info("Manifest loaded")
        if cfn.does_stack_exist(stack_name=f"orbit-{context.name}") is False:
            msg_ctx.error("Please, deploy your environment before deploy/destroy any docker image")
            return

        msg_ctx.progress(3)

        delete.delete_image(env_name=env, image_name=name)

        msg_ctx.info("Docker Image destroyed from ECR")
        msg_ctx.progress(100)


def delete_podsetting(namespace: str, podsetting_name: str, debug: bool) -> None:
    with MessagesContext("Podsetting Deleted", debug=debug) as msg_ctx:
        msg_ctx.info("Recieved request to delete podsetting")
        _logger.debug(f"Recieved request to delete podsetting {podsetting_name} in namespace {namespace}")
        try:
            import aws_orbit_sdk.controller as controller

            controller.delete_podsetting(namespace=namespace, podsetting_name=podsetting_name)
        except ImportError:
            raise ImportError("Make sure the Orbit SDK is installed")
        msg_ctx.tip("Podsetting deleted")
        msg_ctx.progress(100)
        return
