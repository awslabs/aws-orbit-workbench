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
from typing import Optional, cast

import botocore.exceptions
import click

from aws_orbit.messages import MessagesContext
from aws_orbit.models.context import Context, ContextSerDe, FoundationContext
from aws_orbit.remote_files import destroy
from aws_orbit.services import cfn, elb, s3, secretsmanager, ssm

_logger: logging.Logger = logging.getLogger(__name__)


def destroy_toolkit(
    env_name: str,
    top_level: str = "orbit",
    cdk_toolkit_bucket: Optional[str] = None,
) -> None:
    try:
        if cdk_toolkit_bucket:
            s3.delete_bucket(bucket=cdk_toolkit_bucket)
    except Exception as ex:
        _logger.debug("Skipping CDK Toolkit bucket deletion. Cause: %s", ex)
    toolkit_stack_name: str = f"{top_level}-{env_name}-toolkit"
    if cfn.does_stack_exist(stack_name=toolkit_stack_name):
        cfn.destroy_stack(stack_name=toolkit_stack_name)
    ssm.cleanup_env(env_name=env_name, top_level=top_level)


def destroy_images(env: str) -> None:
    destroy.destroy_images(env=env)


def destroy_remaining_resources(env_name: str, top_level: str = "orbit") -> None:
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

        msg_ctx.progress(15)
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
        msg_ctx.info("Context loaded")
        msg_ctx.info(f"Teams: {','.join([t.name for t in context.teams])}")
        msg_ctx.progress(25)

        if any(cfn.does_stack_exist(stack_name=t.stack_name) for t in context.teams):
            destroy.destroy_teams(env_name=context.name)
        msg_ctx.progress(95)

        msg_ctx.info("Teams Destroyed")
        msg_ctx.progress(100)


def destroy_env(env: str, preserve_credentials: bool, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as msg_ctx:
        ssm.cleanup_changeset(env_name=env)
        ssm.cleanup_manifest(env_name=env)

        if ssm.does_parameter_exist(name=f"/orbit/{env}/context") is False:
            msg_ctx.info(f"Environment {env} not found. Destroying only possible remaining resources.")
            elb.delete_load_balancers(env_name=env)
            destroy_remaining_resources(env_name=env, top_level="orbit")
            msg_ctx.progress(100)
            return

        msg_ctx.progress(5)
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
        msg_ctx.info("Context loaded")
        msg_ctx.info(f"Teams: {','.join([t.name for t in context.teams])}")

        if any(cfn.does_stack_exist(stack_name=t.stack_name) for t in context.teams):
            raise click.ClickException("Found Teams dependent on the Envrionment.")

        if (
            cfn.does_stack_exist(stack_name=context.env_stack_name)
            or cfn.does_stack_exist(stack_name=context.toolkit.stack_name)
            or cfn.does_stack_exist(stack_name=context.cdk_toolkit.stack_name)
        ):
            msg_ctx.progress(15)
            destroy.destroy_env(env_name=context.name)

        if not preserve_credentials:
            secretsmanager.delete_docker_credentials(secret_id=f"orbit-{context.name}-docker-credentials")
            _logger.info("Removed docker credentials from SecretsManager")

        msg_ctx.info("Env destroyed")
        msg_ctx.progress(95)

        try:
            destroy_toolkit(
                env_name=context.name,
                cdk_toolkit_bucket=context.cdk_toolkit.s3_bucket,
            )
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
        ssm.cleanup_changeset(env_name=env, top_level="orbit-f")
        ssm.cleanup_manifest(env_name=env, top_level="orbit-f")

        if ssm.does_parameter_exist(name=f"/orbit-f/{env}/context") is False:
            msg_ctx.info(f"Foundation {env} not found. Destroying only possible remaining resources.")
            destroy_remaining_resources(env_name=env, top_level="orbit-f")
            msg_ctx.progress(100)
            return

        context: "FoundationContext" = ContextSerDe.load_context_from_ssm(env_name=env, type=FoundationContext)
        msg_ctx.info("Context loaded")
        msg_ctx.progress(25)

        if (
            cfn.does_stack_exist(stack_name=cast(str, context.stack_name))
            or cfn.does_stack_exist(stack_name=context.toolkit.stack_name)
            or cfn.does_stack_exist(stack_name=context.cdk_toolkit.stack_name)
        ):
            destroy.destroy_foundation(env_name=context.name)

        msg_ctx.info("Foundation destroyed")
        msg_ctx.progress(75)

        try:
            destroy_toolkit(
                env_name=context.name,
                top_level="orbit-f",
                cdk_toolkit_bucket=context.cdk_toolkit.s3_bucket,
            )
        except botocore.exceptions.ClientError as ex:
            error = ex.response["Error"]
            if "does not exist" not in error["Message"]:
                raise
            _logger.debug(f"Skipping toolkit destroy: {error['Message']}")
        msg_ctx.info("Toolkit destroyed")
        ssm.cleanup_env(env_name=context.name, top_level="orbit-f")

        msg_ctx.progress(100)


def destroy_credentials(env: str, registry: str, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as msg_ctx:
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
        msg_ctx.info("Context loaded")
        msg_ctx.progress(2)

        if any(cfn.does_stack_exist(stack_name=t.stack_name) for t in context.teams):
            destroy.destroy_credentials(env_name=env, registry=registry)
        msg_ctx.progress(95)

        msg_ctx.info("Registry Credentials Destroyed")
        msg_ctx.progress(100)
