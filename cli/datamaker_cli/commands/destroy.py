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

from datamaker_cli import bundle, plugins, remote
from datamaker_cli.manifest import Manifest, read_manifest_file
from datamaker_cli.messages import MessagesContext
from datamaker_cli.services import cfn, codebuild, s3

_logger: logging.Logger = logging.getLogger(__name__)


def destroy_toolkit(manifest: Manifest) -> None:
    stack_name = f"datamaker-{manifest.name}-toolkit"
    if cfn.does_stack_exist(manifest=manifest, stack_name=stack_name):
        s3.delete_bucket(manifest=manifest, bucket=manifest.toolkit_s3_bucket)
        cfn.destroy_stack(manifest=manifest, stack_name=stack_name)


def destroy_image(filename: str, name: str, debug: bool) -> None:
    with MessagesContext("Destroying Docker Image", debug=debug) as ctx:
        manifest = read_manifest_file(filename=filename)
        ctx.info(f"Manifest loaded: {filename}")
        if cfn.does_stack_exist(manifest=manifest, stack_name=f"datamaker-{manifest.name}") is False:
            ctx.error("Please, deploy your environment before deploy/destroy any docker image")
            return
        bundle_path = bundle.generate_bundle(command_name=f"destroy_image-{name}", manifest=manifest, dirs=[])
        ctx.progress(3)
        buildspec = codebuild.generate_spec(
            manifest=manifest,
            plugins=False,
            cmds_build=[f"datamaker remote --command destroy_image {name}"],
        )
        remote.run(
            command_name=f"destroy_image-{name}",
            manifest=manifest,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=ctx.progress_bar_callback,
            timeout=10,
        )
        ctx.info("Docker Image destroyed from ECR")
        ctx.progress(100)


def destroy(filename: str, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as ctx:
        manifest = read_manifest_file(filename=filename)
        ctx.info(f"Manifest loaded: {filename}")
        ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        ctx.progress(2)

        plugins.load_plugins(manifest=manifest)
        ctx.info(f"Plugins: {','.join([p.name for p in manifest.plugins])}")
        ctx.progress(3)

        if cfn.does_stack_exist(
            manifest=manifest, stack_name=f"datamaker-{manifest.name}-demo"
        ) or cfn.does_stack_exist(manifest=manifest, stack_name=f"datamaker-{manifest.name}"):
            manifest.read_ssm()
            bundle_path = bundle.generate_bundle(command_name="destroy", manifest=manifest)
            ctx.progress(5)
            buildspec = codebuild.generate_spec(
                manifest=manifest,
                plugins=True,
                cmds_build=["datamaker remote --command destroy"],
            )
            remote.run(
                command_name="destroy",
                manifest=manifest,
                bundle_path=bundle_path,
                buildspec=buildspec,
                codebuild_log_callback=ctx.progress_bar_callback,
                timeout=30,
            )
        ctx.info("Env destroyed")
        ctx.progress(95)

        destroy_toolkit(manifest=manifest)
        ctx.info("Toolkit destroyed")
        ctx.progress(100)
