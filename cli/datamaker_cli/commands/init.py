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
from typing import Optional

from datamaker_cli import DATAMAKER_CLI_ROOT, utils
from datamaker_cli.messages import MessagesContext, stylize
import shutil
_logger: logging.Logger = logging.getLogger(__name__)


def create_manifest(
    name: str,
    filename: str,
    region: Optional[str],
    demo: bool,
    dev: bool,
) -> None:
    region_str: str = region if region is not None else utils.get_region()
    input = os.path.join(DATAMAKER_CLI_ROOT, "data", "init", "default-manifest.yaml")
    with open(input, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        region=region_str,
        name=name,
        demo="true" if demo else False,
        dev="true" if dev else False,
        images_source="code" if dev else "dockerhub",
        jupyter_hub_repository="../images/jupyter-hub/" if dev else "aws-datamaker-jupyter-hub",
        jupyter_user_repository="../images/jupyter-user/" if dev else "aws-datamaker-jupyter-user",
        landing_page_repository="../images/landing-page/" if dev else "aws-datamaker-landing-page",
    )

    with open(filename, "w") as file:
        file.write(content)

def init(name: str, region: Optional[str], demo: bool, dev: bool, debug: bool) -> None:
    conf_dir = "conf"
    with MessagesContext("Initializing", debug=debug) as ctx:
        conf_dir_src = os.path.join(DATAMAKER_CLI_ROOT, "data", "init")
        if os.path.exists(conf_dir):
            shutil.rmtree(conf_dir)
        shutil.copytree(src=conf_dir_src, dst=conf_dir, ignore=shutil.ignore_patterns("default-manifest.yaml"))
        ctx.progress(50)
        name = name.lower()
        filename: str = os.path.join(conf_dir, f"{name}.yaml")
        create_manifest(name=name, filename=filename, demo=demo, dev=dev, region=region)
        ctx.info(f"Manifest generated as {filename}")
        ctx.progress(100)
        if demo:
            ctx.tip(f"Recommended next step: {stylize(f'datamaker deploy -f {filename}')}")
        else:
            ctx.tip(
                f"Fill up the manifest file ({filename}) " f"and run: " f"{stylize(f'datamaker deploy -f {filename}')}"
            )
