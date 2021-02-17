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
import uuid
from typing import TYPE_CHECKING, List, Optional, Tuple, cast

import click

from aws_orbit import bundle, dockerhub, plugins, remote, toolkit
from aws_orbit.messages import MessagesContext, stylize
from aws_orbit.models.changeset import dump_changeset_to_str, extract_changeset
from aws_orbit.models.context import dump_context_to_ssm, load_context_from_manifest, load_context_from_ssm
from aws_orbit.models.manifest import load_manifest_from_file
from aws_orbit.services import cfn, codebuild

if TYPE_CHECKING:
    from aws_orbit.models.changeset import Changeset
    from aws_orbit.models.context import Context
    from aws_orbit.models.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def _request_dockerhub_credential(msg_ctx: MessagesContext) -> Tuple[str, str]:
    if msg_ctx.pbar is not None:
        msg_ctx.pbar.clear()
    username = cast(
        str,
        click.prompt("Please enter the DockerHub username", type=str, hide_input=False),
    )
    password = cast(
        str,
        click.prompt("Please enter the DockerHub password", type=str, hide_input=True),
    )
    return username, password


def _get_images_dirs(context: "Context", manifest_filename: str, skip_images: bool) -> List[Tuple[str, str]]:
    if skip_images:
        dirs: List[Tuple[str, str]] = []
    else:
        refdir: str = os.path.dirname(os.path.abspath(manifest_filename))
        _logger.debug("refdir: %s", refdir)
        _logger.debug(context.images.jupyter_hub.source)
        dirs = [
            (os.path.join(refdir, getattr(context.images, name).path), name.replace("_", "-"))
            for name in context.images.names
            if getattr(context.images, name).source == "code"
        ]
        _logger.debug("dirs: %s", dirs)
    return dirs


def deploy_toolkit(
    context: "Context",
    username: Optional[str],
    password: Optional[str],
    msg_ctx: MessagesContext,
) -> None:
    credential_received: bool = username is not None and password is not None
    stack_exist: bool = cfn.does_stack_exist(stack_name=context.toolkit.stack_name)
    credential_exist: bool = dockerhub.does_credential_exist(context=context) if stack_exist else False

    if stack_exist:
        if not credential_exist and not credential_received:
            username, password = _request_dockerhub_credential(msg_ctx=msg_ctx)
            dockerhub.store_credential(context=context, username=username, password=password)
            credential_exist = True
        elif credential_received:
            dockerhub.store_credential(
                context=context,
                username=cast(str, username),
                password=cast(str, password),
            )
            credential_exist = True
    else:
        context.toolkit.deploy_id = uuid.uuid4().hex[:6]
        if not credential_received:
            username, password = _request_dockerhub_credential(msg_ctx=msg_ctx)
            credential_exist = False

    msg_ctx.progress(6)
    _logger.debug("context.toolkit.deploy_id: %s", context.toolkit.deploy_id)
    template_filename: str = toolkit.synth(context=context)
    cfn.deploy_template(
        stack_name=context.toolkit.stack_name, filename=template_filename, env_tag=context.env_tag, s3_bucket=None
    )
    context.fetch_toolkit_data()
    dump_context_to_ssm(context=context)

    if credential_exist is False:
        dockerhub.store_credential(
            context=context,
            username=cast(str, username),
            password=cast(str, password),
        )


def deploy_foundation(
    filename: str,
    debug: bool,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        manifest: "Manifest" = load_manifest_from_file(filename=filename)
        msg_ctx.info(f"Manifest loaded: {filename}")
        msg_ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        msg_ctx.progress(3)

        context: "Context" = load_context_from_manifest(manifest=manifest)
        msg_ctx.info("Current Context loaded")
        msg_ctx.info(f"Teams: {','.join([t.name for t in context.teams])}")
        msg_ctx.progress(4)

        _logger.debug("Inspecting possible manifest changes...")
        changeset: "Changeset" = extract_changeset(manifest=manifest, context=context, msg_ctx=msg_ctx)
        _logger.debug(f"Changeset:\n{dump_changeset_to_str(changeset=changeset)}")
        msg_ctx.progress(5)

        deploy_toolkit(
            context=context,
            username=username,
            password=password,
            msg_ctx=msg_ctx,
        )
        msg_ctx.info("Toolkit deployed")
        msg_ctx.progress(8)

        bundle_path = bundle.generate_bundle(command_name="deploy_foundation", context=context, changeset=changeset)
        msg_ctx.progress(10)
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=True,
            cmds_build=[f"orbit remote --command deploy_foundation {context.name}"],
            changeset=changeset,
        )
        msg_ctx.progress(11)
        remote.run(
            command_name="deploy_foundation",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=90,
        )
        msg_ctx.info("Orbit Foundation deployed")
        msg_ctx.progress(100)


def deploy_env(
    filename: str,
    skip_images: bool,
    env_only: bool,
    debug: bool,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        manifest: "Manifest" = load_manifest_from_file(filename=filename)
        msg_ctx.info(f"Manifest loaded: {filename}")
        msg_ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        msg_ctx.progress(3)

        context: "Context" = load_context_from_manifest(manifest=manifest)
        msg_ctx.info("Current Context loaded")
        msg_ctx.info(f"Teams: {','.join([t.name for t in context.teams])}")
        msg_ctx.progress(4)

        _logger.debug("Inspecting possible manifest changes...")
        changeset: "Changeset" = extract_changeset(manifest=manifest, context=context, msg_ctx=msg_ctx)
        _logger.debug(f"Changeset:\n{dump_changeset_to_str(changeset=changeset)}")
        msg_ctx.progress(5)

        plugins.PLUGINS_REGISTRIES.load_plugins(
            context=context,
            msg_ctx=msg_ctx,
            plugin_changesets=changeset.plugin_changesets,
            teams_changeset=changeset.teams_changeset,
        )
        msg_ctx.progress(7)

        deploy_toolkit(
            context=context,
            username=username,
            password=password,
            msg_ctx=msg_ctx,
        )
        msg_ctx.info("Toolkit deployed")
        msg_ctx.progress(10)

        bundle_path = bundle.generate_bundle(
            command_name="deploy",
            context=context,
            dirs=_get_images_dirs(context=context, manifest_filename=filename, skip_images=skip_images),
            changeset=changeset,
        )
        msg_ctx.progress(11)
        skip_images_remote_flag: str = "skip-images" if skip_images else "no-skip-images"
        env_only_flag: str = "env-stacks" if env_only else "all-stacks"
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=True,
            cmds_build=[f"orbit remote --command deploy {context.name} {skip_images_remote_flag} {env_only_flag}"],
            changeset=changeset,
        )
        remote.run(
            command_name="deploy",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=90,
        )
        msg_ctx.info("Orbit Workbench deployed")
        msg_ctx.progress(98)

        if cfn.does_stack_exist(stack_name=context.demo_stack_name):
            context = load_context_from_manifest(manifest=manifest)
            msg_ctx.info(f"Context updated: {filename}")
        msg_ctx.progress(99)

        if context.cognito_users_url:
            msg_ctx.tip(f"Add users: {stylize(context.cognito_users_url, underline=True)}")
        else:
            RuntimeError("Cognito Users URL not found.")
        if context.landing_page_url:
            msg_ctx.tip(f"Access Orbit Workbench: {stylize(context.landing_page_url, underline=True)}")
        else:
            RuntimeError("Landing Page URL not found.")
        msg_ctx.progress(100)


def _deploy_image(env: str, dir: str, name: str, script: Optional[str], build_args: Optional[List[str]], region: Optional[str], debug: bool) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as msg_ctx:
        context: "Context" = load_context_from_ssm(env_name=env)

        if cfn.does_stack_exist(stack_name=f"orbit-{context.name}") is False:
            msg_ctx.error("Please, deploy your environment before deploy any addicional docker image")
            return

        plugins.PLUGINS_REGISTRIES.load_plugins(
            context=context,
            msg_ctx=msg_ctx,
            plugin_changesets=[],
            teams_changeset=None,
        )
        msg_ctx.progress(3)

        bundle_path = bundle.generate_bundle(
            command_name=f"deploy_image-{name}", context=context, dirs=[(dir, name)], changeset=None
        )
        msg_ctx.progress(4)
        script_str = "NO_SCRIPT" if script is None else script
        build_args = [] if build_args is None else build_args
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=True,
            cmds_build=[f"orbit remote --command _deploy_image {env} {name} {script_str} {' '.join(build_args)}"],
            changeset=None,
        )
        remote.run(
            command_name=f"deploy_image-{name}",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=10,
        )
        msg_ctx.info("Docker Image deploy into ECR")
        address = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}-{name}"
        msg_ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        msg_ctx.progress(100)
