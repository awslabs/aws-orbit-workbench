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
from aws_orbit import bundle, cleanup, plugins, remote
from aws_orbit.changeset import Changeset, extract_changeset
from aws_orbit.manifest import Manifest
from aws_orbit.messages import MessagesContext
from aws_orbit.services import cfn, codebuild, elb, s3, vpc

_logger: logging.Logger = logging.getLogger(__name__)


def destroy_toolkit(manifest: Manifest) -> None:
    if manifest.toolkit_s3_bucket is None:
        if manifest.toolkit_s3_bucket is None:
            s3.delete_bucket_by_prefix(
                manifest=manifest, prefix=f"orbit-{manifest.name}-toolkit-{manifest.account_id}-"
            )
        else:
            try:
                s3.delete_bucket(manifest=manifest, bucket=manifest.toolkit_s3_bucket)
            except Exception as ex:
                _logger.debug("Skipping Toolkit bucket deletion. Cause: %s", ex)
    if cfn.does_stack_exist(manifest=manifest, stack_name=manifest.toolkit_stack_name):
        cfn.destroy_stack(manifest=manifest, stack_name=manifest.toolkit_stack_name)


def destroy_remaining_resources(manifest: Manifest, keep_demo: bool) -> None:
    if keep_demo:
        elb.delete_load_balancers(manifest=manifest)
    else:
        if cfn.does_stack_exist(manifest=manifest, stack_name=manifest.demo_stack_name):
            try:
                vpc_id: str = vpc.get_env_vpc_id(manifest=manifest)
                cleanup.demo_remaining_dependencies(manifest=manifest, vpc_id=vpc_id)
            except:  # noqa
                _logger.debug("VPC not found.")
            cfn.destroy_stack(manifest=manifest, stack_name=manifest.demo_stack_name)
        s3.delete_bucket_by_prefix(
            manifest=manifest, prefix=f"orbit-{manifest.name}-cdk-toolkit-{manifest.account_id}-"
        )
        env_cdk_toolkit: str = f"orbit-{manifest.name}-cdk-toolkit"
        if cfn.does_stack_exist(manifest=manifest, stack_name=env_cdk_toolkit):
            cfn.destroy_stack(manifest=manifest, stack_name=env_cdk_toolkit)
        destroy_toolkit(manifest=manifest)


def destroy(env: str, teams_only: bool, keep_demo: bool, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as ctx:
        manifest = Manifest(filename=None, env=env, region=None)
        if manifest.raw_ssm is None and teams_only is False:
            ctx.info(f"Environment {env} not found")
            destroy_remaining_resources(manifest=manifest, keep_demo=keep_demo)
            ctx.progress(100)
            return

        manifest.fillup()
        ctx.info("Manifest loaded")
        ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        ctx.progress(2)

        _logger.debug("Inspecting possible manifest changes...")
        changes: Changeset = extract_changeset(manifest=manifest, ctx=ctx)
        _logger.debug(f"Changeset: {changes.asdict()}")
        ctx.progress(3)

        plugins.PLUGINS_REGISTRIES.load_plugins(
            manifest=manifest,
            ctx=ctx,
            plugin_changesets=changes.plugin_changesets,
            teams_changeset=changes.teams_changeset,
        )
        ctx.progress(4)

        if (
            cfn.does_stack_exist(manifest=manifest, stack_name=manifest.demo_stack_name)
            or cfn.does_stack_exist(manifest=manifest, stack_name=manifest.env_stack_name)
            or cfn.does_stack_exist(manifest=manifest, stack_name=manifest.cdk_toolkit_stack_name)
        ):
            bundle_path = bundle.generate_bundle(command_name="destroy", manifest=manifest, changeset=changes)
            ctx.progress(5)
            flags = "teams-stacks" if teams_only else "keep-demo" if keep_demo else "all-stacks"

            buildspec = codebuild.generate_spec(
                manifest=manifest,
                plugins=True,
                cmds_build=[f"orbit remote --command destroy {env} {flags}"],
                changeset=changes,
            )
            remote.run(
                command_name="destroy",
                manifest=manifest,
                bundle_path=bundle_path,
                buildspec=buildspec,
                codebuild_log_callback=ctx.progress_bar_callback,
                timeout=45,
            )
        if teams_only:
            ctx.info("Env Skipped")
        else:
            ctx.info("Env destroyed")
        ctx.progress(95)

        try:
            if not teams_only and not keep_demo:
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
