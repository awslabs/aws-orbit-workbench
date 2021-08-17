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

import json
import logging
from typing import List, Optional

from aws_orbit import bundle, remote
from aws_orbit.messages import MessagesContext, stylize
from aws_orbit.models.context import Context, ContextSerDe
from aws_orbit.services import cfn, codebuild

_logger: logging.Logger = logging.getLogger(__name__)


def build_image(
    env: str,
    dir: Optional[str],
    name: str,
    script: Optional[str],
    build_args: Optional[List[str]],
    timeout: int = 30,
    debug: bool = False,
    source_registry: Optional[str] = None,
    source_repository: Optional[str] = None,
    source_version: Optional[str] = None,
) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as msg_ctx:
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
        msg_ctx.info("Manifest loaded")
        if cfn.does_stack_exist(stack_name=f"orbit-{context.name}") is False:
            msg_ctx.error("Please, deploy your environment before deploying any additional docker image")
            return
        msg_ctx.progress(3)
        if dir:
            dirs = [(dir, name)]
        else:
            dirs = []
        bundle_path = bundle.generate_bundle(command_name=f"deploy_image-{name}", context=context, dirs=dirs)
        msg_ctx.progress(5)

        script_str = "NO_SCRIPT" if script is None else script
        source_str = "NO_REPO" if source_registry is None else f"{source_registry} {source_repository} {source_version}"
        build_args = [] if build_args is None else build_args
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=False,
            cmds_build=[
                f"orbit remote --command build_image " f"{env} {name} {script_str} {source_str} {' '.join(build_args)}"
            ],
            changeset=None,
        )
        msg_ctx.progress(6)

        remote.run(
            command_name=f"deploy_image-{name}",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=timeout,
        )
        msg_ctx.info("Docker Image deploy into ECR")

        address = (
            f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}/{name}"
            if name in [n.replace("_", "-") for n in context.images.names]
            else f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}/users/{name}"
        )

        msg_ctx.info(f"ECR Image Address={address}")
        msg_ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        msg_ctx.progress(100)


def build_podsetting(
    env_name: str,
    team_name: str,
    podsetting: str,
    debug: bool = False,
) -> None:
    # Do some quick validation and fail fast
    with MessagesContext("Creating PodSetting", debug=debug) as msg_ctx:
        ps = json.loads(podsetting)
        msg_ctx.progress(3)
        _logger.debug(ps)
        if not ps["description"] or not ps["name"]:
            print("raise an error...")
            msg_ctx.error("Please, make sure the fields description and name are present")
            return
        ps_name = ps["name"]
        msg_ctx.progress(10)
        resources = ps.get("resources", None)
        if resources is not None:
            if (
                "nvidia.com/gpu" in resources["limits"]
                or "nvidia.com/gpu" in resources["requests"]
                or "node.kubernetes.io/instance-type" in resources["requests"]
                or "node.kubernetes.io/instance-type" in resources["limits"]
            ):
                if ps.get("node-group") is None and ps.get("instance-type") is None:
                    msg_ctx.error(
                        "If you request a GPU, please define a node-group or instance-type to match your cluster / GPU"
                    )
                    return
        msg_ctx.info("JSON payload validated")
        msg_ctx.progress(15)
        # Looks ok...call the SDK to build and deploy
        try:
            import aws_orbit_sdk.controller as controller

            controller.build_podsetting(env_name=env_name, team_name=team_name, podsetting=podsetting, debug=debug)
        except ImportError:
            raise ImportError("Make sure the Orbit SDK is installed")

        msg_ctx.info(f"PodSetting {ps_name} created")
        msg_ctx.progress(100)
