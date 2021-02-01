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
import shutil
from typing import Optional

from aws_orbit import ORBIT_CLI_ROOT, utils
from aws_orbit.messages import MessagesContext, stylize

_logger: logging.Logger = logging.getLogger(__name__)


def write_resolve_parameters(
    manifest_name: str,
    name: str,
    filename: str,
    region: Optional[str],
) -> None:
    region_str: str = region if region is not None else utils.get_region()
    input = os.path.join(ORBIT_CLI_ROOT, "data", "init", manifest_name)
    with open(input, "r") as file:
        content: str = file.read()
    content = utils.resolve_parameters(content, dict(region=region_str, name=name))

    with open(filename, "w") as file:
        file.write(content)


def init(name: str, region: Optional[str], foundation: bool, debug: bool) -> None:
    conf_dir = "conf"
    with MessagesContext("Initializing", debug=debug) as ctx:
        conf_dir_src = os.path.join(ORBIT_CLI_ROOT, "data", "init")
        if os.path.exists(conf_dir):
            shutil.rmtree(conf_dir)
        foundation_manifest = "default-foundation.yaml"
        env_manifest = "default-env-manifest.yaml"
        shutil.copytree(src=conf_dir_src, dst=conf_dir)
        ctx.progress(50)
        name = name.lower()

        write_resolve_parameters(
            name=name,
            filename=os.path.join(conf_dir, foundation_manifest),
            region=region,
            manifest_name=foundation_manifest,
        )
        write_resolve_parameters(
            name=name, filename=os.path.join(conf_dir, env_manifest), region=region, manifest_name=env_manifest
        )
        ctx.info("Env Manifest generated into conf folder")

        ctx.progress(100)
        if foundation:
            ctx.tip(f"Recommended next step: {stylize(f'orbit deploy foundation -f {foundation_manifest}')}")

        ctx.tip(
            f"Then, fill up the manifest file ({env_manifest}) "
            f"and run: "
            f"{stylize(f'orbit env -f {env_manifest}')}"
        )
