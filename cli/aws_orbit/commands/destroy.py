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
from typing import TYPE_CHECKING

import botocore.exceptions

from aws_orbit import bundle, cleanup, plugins, remote, utils
from aws_orbit.messages import MessagesContext
from aws_orbit.models.context import load_context_from_ssm
from aws_orbit.services import cfn, codebuild, elb, s3, ssm, vpc

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def destroy_toolkit(env_name: str) -> None:
    try:
        s3.delete_bucket_by_prefix(prefix=f"orbit-{env_name}-toolkit-{utils.get_account_id()}-")
    except Exception as ex:
        _logger.debug("Skipping Toolkit bucket deletion. Cause: %s", ex)
    toolkit_stack_name: str = f"orbit-{env_name}-toolkit"
    if cfn.does_stack_exist(stack_name=toolkit_stack_name):
        cfn.destroy_stack(stack_name=toolkit_stack_name)
    ssm.cleanup_env(env_name=env_name)


def destroy_remaining_resources(env_name: str, keep_demo: bool) -> None:
    if keep_demo:
        elb.delete_load_balancers(env_name=env_name)
    else:
        demo_stack_name = f"orbit-{env_name}-demo"
        if cfn.does_stack_exist(stack_name=demo_stack_name):
            try:
                vpc_id: str = vpc.get_env_vpc_id(env_name=env_name)
                cleanup.demo_remaining_dependencies_contextless(env_name=env_name, vpc_id=vpc_id)
            except:  # noqa
                _logger.debug("VPC not found.")
            cfn.destroy_stack(stack_name=demo_stack_name)
        s3.delete_bucket_by_prefix(prefix=f"orbit-{env_name}-cdk-toolkit-{utils.get_account_id()}-")
        env_cdk_toolkit: str = f"orbit-{env_name}-cdk-toolkit"
        if cfn.does_stack_exist(stack_name=env_cdk_toolkit):
            cfn.destroy_stack(stack_name=env_cdk_toolkit)
        destroy_toolkit(env_name=env_name)


def destroy_all(env: str, teams_only: bool, keep_demo: bool, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as msg_ctx:
        ssm.cleanup_changeset(env_name=env)
        ssm.cleanup_manifest(env_name=env)

        if ssm.does_parameter_exist(name=f"/orbit/{env}/context") is False:
            msg_ctx.info(f"Environment {env} not found. Destroying only possible remaining resources.")
            destroy_remaining_resources(env_name=env, keep_demo=keep_demo)
            msg_ctx.progress(100)
            return

        context: "Context" = load_context_from_ssm(env_name=env)
        msg_ctx.info("Context loaded")
        msg_ctx.info(f"Teams: {','.join([t.name for t in context.teams])}")
        msg_ctx.progress(2)

        plugins.PLUGINS_REGISTRIES.load_plugins(
            context=context,
            msg_ctx=msg_ctx,
            plugin_changesets=[],
            teams_changeset=None,
        )
        msg_ctx.progress(4)

        if (
            cfn.does_stack_exist(stack_name=context.demo_stack_name)
            or cfn.does_stack_exist(stack_name=context.env_stack_name)
            or cfn.does_stack_exist(stack_name=context.cdk_toolkit.stack_name)
        ):
            bundle_path = bundle.generate_bundle(command_name="destroy", context=context, changeset=None, plugins=True)
            msg_ctx.progress(5)
            flags = "teams-stacks" if teams_only else "keep-demo" if keep_demo else "all-stacks"

            buildspec = codebuild.generate_spec(
                context=context,
                plugins=True,
                cmds_build=[f"orbit remote --command destroy {env} {flags}"],
                changeset=None,
            )
            remote.run(
                command_name="destroy",
                context=context,
                bundle_path=bundle_path,
                buildspec=buildspec,
                codebuild_log_callback=msg_ctx.progress_bar_callback,
                timeout=45,
            )
        if teams_only:
            msg_ctx.info("Env Skipped")
        else:
            msg_ctx.info("Env destroyed")
        msg_ctx.progress(95)

        if teams_only is False and keep_demo is False:
            try:
                destroy_toolkit(env_name=context.name)
            except botocore.exceptions.ClientError as ex:
                error = ex.response["Error"]
                if "does not exist" not in error["Message"]:
                    raise
                _logger.debug(f"Skipping toolkit destroy: {error['Message']}")
            msg_ctx.info("Toolkit destroyed")
            ssm.cleanup_env(env_name=context.name)
        else:
            msg_ctx.info("Toolkit skipped")

        msg_ctx.progress(100)
