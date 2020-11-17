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

import botocore.exceptions

from datamaker_cli import bundle, plugins, remote
from datamaker_cli.changeset import Changeset, extract_changeset
from datamaker_cli.manifest import Manifest
from datamaker_cli.messages import MessagesContext
from datamaker_cli.services import cfn, codebuild, s3

_logger: logging.Logger = logging.getLogger(__name__)


def destroy_toolkit(manifest: Manifest) -> None:
    if manifest.toolkit_s3_bucket is None:
        manifest.fillup()
        if manifest.toolkit_s3_bucket is None:
            _logger.debug("Skipping Toolkit destroy. Because manifest.toolkit_s3_bucket is None")
            return
    if cfn.does_stack_exist(manifest=manifest, stack_name=manifest.toolkit_stack_name):
        try:
            s3.delete_bucket(manifest=manifest, bucket=manifest.toolkit_s3_bucket)
        except Exception as ex:
            _logger.debug("Skipping Toolkit bucket deletion. Cause: %s", ex)
        cfn.destroy_stack(manifest=manifest, stack_name=manifest.toolkit_stack_name)


def destroy(filename: str, teams_only: bool, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as ctx:
        manifest = Manifest(filename=filename)
        manifest.fillup()
        ctx.info(f"Manifest loaded: {filename}")
        ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        ctx.progress(2)

        _logger.debug("Inspecting possible manifest changes...")
        changes: Changeset = extract_changeset(manifest=manifest, ctx=ctx)
        _logger.debug(f"Changeset: {changes.asdict()}")
        ctx.progress(3)

        plugins.PLUGINS_REGISTRIES.load_plugins(manifest=manifest, ctx=ctx, changes=changes.plugin_changesets)
        ctx.progress(4)

        if (
            cfn.does_stack_exist(manifest=manifest, stack_name=manifest.demo_stack_name)
            or cfn.does_stack_exist(manifest=manifest, stack_name=manifest.env_stack_name)
            or cfn.does_stack_exist(manifest=manifest, stack_name=manifest.cdk_toolkit_stack_name)
        ):
            bundle_path = bundle.generate_bundle(command_name="destroy", manifest=manifest, changeset=changes)
            ctx.progress(5)
            teams_only_flag = "teams-stacks" if teams_only else "all-stacks"
            buildspec = codebuild.generate_spec(
                manifest=manifest,
                plugins=True,
                cmds_build=[f"datamaker remote --command destroy {teams_only_flag}"],
                changeset=changes,
            )
            remote.run(
                command_name="destroy",
                manifest=manifest,
                bundle_path=bundle_path,
                buildspec=buildspec,
                codebuild_log_callback=ctx.progress_bar_callback,
                timeout=30,
            )
        if teams_only:
            ctx.info("Env Skipped")
        else:
            ctx.info("Env destroyed")
        ctx.progress(95)

        try:
            if not teams_only:
                destroy_toolkit(manifest=manifest)
        except botocore.exceptions.ClientError as ex:
            error = ex.response["Error"]
            if "does not exist" not in error["Message"]:
                raise
            _logger.debug(f"Skipping toolkit destroy: {error['Message']}")
        if teams_only:
            ctx.info("Toolkit skipped")
        else:
            ctx.info("Toolkit destroyed")
        ctx.progress(100)
