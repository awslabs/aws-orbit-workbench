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
from typing import cast

import botocore.exceptions

from aws_orbit import bundle, plugins, remote, utils
from aws_orbit.messages import MessagesContext
from aws_orbit.models.context import Context, ContextSerDe, FoundationContext
from aws_orbit.services import cfn, codebuild, elb, s3, ssm

_logger: logging.Logger = logging.getLogger(__name__)


def destroy_toolkit(env_name: str, top_level: str = "orbit") -> None:
    try:
        s3.delete_bucket_by_prefix(prefix=f"{top_level}-{env_name}-toolkit-{utils.get_account_id()}-")
    except Exception as ex:
        _logger.debug("Skipping Toolkit bucket deletion. Cause: %s", ex)
    toolkit_stack_name: str = f"{top_level}-{env_name}-toolkit"
    if cfn.does_stack_exist(stack_name=toolkit_stack_name):
        cfn.destroy_stack(stack_name=toolkit_stack_name)
    ssm.cleanup_env(env_name=env_name, top_level=top_level)


def destroy_remaining_resources(env_name: str, top_level: str = "orbit") -> None:
    s3.delete_bucket_by_prefix(prefix=f"{top_level}-{env_name}-cdk-toolkit-{utils.get_account_id()}-")
    env_cdk_toolkit: str = f"{top_level}-{env_name}-cdk-toolkit"
    if cfn.does_stack_exist(stack_name=env_cdk_toolkit):
        cfn.destroy_stack(stack_name=env_cdk_toolkit)
    destroy_toolkit(env_name=env_name)


def destroy_teams(env: str, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as msg_ctx:
        ssm.cleanup_changeset(env_name=env)

        if not ssm.list_parameters(prefix=f"/orbit/{env}/teams/"):
            msg_ctx.info(f"No {env} Teams found.")
            msg_ctx.progress(100)
            return

        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
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

        if any(cfn.does_stack_exist(stack_name=t.stack_name) for t in context.teams):
            bundle_path = bundle.generate_bundle(command_name="destroy", context=context)
            msg_ctx.progress(5)

            buildspec = codebuild.generate_spec(
                context=context,
                plugins=True,
                cmds_build=[f"orbit remote --command destroy_teams {env}"],
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
        msg_ctx.progress(95)

        msg_ctx.info("Teams Destroyed")
        msg_ctx.progress(100)


def destroy_env(env: str, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as msg_ctx:
        ssm.cleanup_changeset(env_name=env)
        ssm.cleanup_manifest(env_name=env)

        if ssm.does_parameter_exist(name=f"/orbit/{env}/context") is False:
            msg_ctx.info(f"Environment {env} not found. Destroying only possible remaining resources.")
            elb.delete_load_balancers(env_name=env)
            destroy_remaining_resources(env_name=env, top_level="orbit")
            msg_ctx.progress(100)
            return

        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
        msg_ctx.info("Context loaded")
        msg_ctx.info(f"Teams: {','.join([t.name for t in context.teams])}")
        msg_ctx.progress(2)

        if any(cfn.does_stack_exist(stack_name=t.stack_name) for t in context.teams):
            msg_ctx.error("Found Teams dependent on the Envrionment.")
            return

        if (
            cfn.does_stack_exist(stack_name=context.env_stack_name)
            or cfn.does_stack_exist(stack_name=context.toolkit.stack_name)
            or cfn.does_stack_exist(stack_name=context.cdk_toolkit.stack_name)
        ):
            bundle_path = bundle.generate_bundle(command_name="destroy", context=context)
            msg_ctx.progress(5)

            buildspec = codebuild.generate_spec(
                context=context,
                plugins=True,
                cmds_build=[f"orbit remote --command destroy_env {env}"],
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

        msg_ctx.info("Env destroyed")
        msg_ctx.progress(95)

        try:
            destroy_toolkit(env_name=context.name)
        except botocore.exceptions.ClientError as ex:
            error = ex.response["Error"]
            if "does not exist" not in error["Message"]:
                raise
            _logger.debug(f"Skipping toolkit destroy: {error['Message']}")
        msg_ctx.info("Toolkit destroyed")
        ssm.cleanup_env(env_name=context.name)

        msg_ctx.progress(100)


def destroy_foundation(env: str, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as msg_ctx:
        ssm.cleanup_changeset(env_name=env, top_level="orbit-foundation")
        ssm.cleanup_manifest(env_name=env, top_level="orbit-foundation")

        if ssm.does_parameter_exist(name=f"/orbit-foundation/{env}/context") is False:
            msg_ctx.info(f"Foundation {env} not found. Destroying only possible remaining resources.")
            destroy_remaining_resources(env_name=env, top_level="orbit-foundation")
            msg_ctx.progress(100)
            return

        context: "FoundationContext" = ContextSerDe.load_context_from_ssm(env_name=env, type=FoundationContext)
        msg_ctx.info("Context loaded")
        msg_ctx.progress(2)

        msg_ctx.progress(4)

        if (
            cfn.does_stack_exist(stack_name=cast(str, context.stack_name))
            or cfn.does_stack_exist(stack_name=context.toolkit.stack_name)
            or cfn.does_stack_exist(stack_name=context.cdk_toolkit.stack_name)
        ):
            bundle_path = bundle.generate_bundle(command_name="destroy", context=cast(Context, context))
            msg_ctx.progress(5)

            buildspec = codebuild.generate_spec(
                context=cast(Context, context),
                plugins=False,
                cmds_build=[f"orbit remote --command destroy_foundation {env}"],
                changeset=None,
            )
            remote.run(
                command_name="destroy",
                context=cast(Context, context),
                bundle_path=bundle_path,
                buildspec=buildspec,
                codebuild_log_callback=msg_ctx.progress_bar_callback,
                timeout=45,
            )
        msg_ctx.info("Foundation destroyed")
        msg_ctx.progress(95)

        try:
            destroy_toolkit(env_name=context.name, top_level="orbit-foundation")
        except botocore.exceptions.ClientError as ex:
            error = ex.response["Error"]
            if "does not exist" not in error["Message"]:
                raise
            _logger.debug(f"Skipping toolkit destroy: {error['Message']}")
        msg_ctx.info("Toolkit destroyed")
        ssm.cleanup_env(env_name=context.name, top_level="orbit-foundation")

        msg_ctx.progress(100)
