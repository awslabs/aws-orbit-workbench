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
from typing import Optional

from datamaker_cli import bundle, remote
from datamaker_cli.manifest import Manifest
from datamaker_cli.messages import MessagesContext, stylize
from datamaker_cli.services import cfn, codebuild

_logger: logging.Logger = logging.getLogger(__name__)


def deploy_image(filename: str, dir: str, name: str, script: Optional[str], debug: bool) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as ctx:
        manifest = Manifest(filename=filename)
        manifest.fillup()
        ctx.info(f"Manifest loaded: {filename}")
        if cfn.does_stack_exist(manifest=manifest, stack_name=f"datamaker-{manifest.name}") is False:
            ctx.error("Please, deploy your environment before deploy any addicional docker image")
            return
        bundle_path = bundle.generate_bundle(command_name=f"deploy_image-{name}", manifest=manifest, dirs=[(dir, name)])
        ctx.progress(3)
        script_str = "" if script is None else script
        buildspec = codebuild.generate_spec(
            manifest=manifest,
            plugins=True,
            cmds_build=[f"datamaker remote --command deploy_image {name} {script_str}"],
        )
        remote.run(
            command_name=f"deploy_image-{name}",
            manifest=manifest,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=ctx.progress_bar_callback,
            timeout=10,
        )
        ctx.info("Docker Image deploy into ECR")
        address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com/datamaker-{manifest.name}-{name}"
        ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        ctx.progress(100)
