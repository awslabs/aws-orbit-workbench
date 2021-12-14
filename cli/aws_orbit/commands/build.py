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

from aws_orbit.messages import MessagesContext

_logger: logging.Logger = logging.getLogger(__name__)


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
