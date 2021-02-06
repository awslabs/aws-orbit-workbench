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
from time import sleep
from typing import List, Optional, Tuple, cast

import click

from aws_orbit import bundle, dockerhub, plugins, remote, toolkit
from aws_orbit.changeset import Changeset, extract_changeset
from aws_orbit.manifest import Manifest
from aws_orbit.messages import MessagesContext, stylize
from aws_orbit.services import cfn, codebuild

_logger: logging.Logger = logging.getLogger(__name__)


def _request_dockerhub_credential(ctx: MessagesContext) -> Tuple[str, str]:
    if ctx.pbar is not None:
        ctx.pbar.clear()
    username = cast(
        str,
        click.prompt("Please enter the DockerHub username", type=str, hide_input=False),
    )
    password = cast(
        str,
        click.prompt("Please enter the DockerHub password", type=str, hide_input=True),
    )
    return username, password


def _get_images_dirs(manifest: Manifest, skip_images: bool) -> List[Tuple[str, str]]:
    if skip_images:
        dirs: List[Tuple[str, str]] = []
    else:
        dirs = [
            (os.path.join(manifest.filename_dir, attrs["path"]), name)
            for name, attrs in manifest.images.items()
            if attrs["source"] == "code"
        ]
        _logger.debug("dirs: %s", dirs)
    return dirs


def deploy_toolkit(
    manifest: Manifest,
    username: Optional[str],
    password: Optional[str],
    ctx: MessagesContext,
) -> None:
    credential_received: bool = username is not None and password is not None
    stack_exist: bool = cfn.does_stack_exist(manifest=manifest, stack_name=manifest.toolkit_stack_name)
    if stack_exist:
        manifest.fetch_toolkit_data()
        credential_exist: bool = dockerhub.does_credential_exist(manifest=manifest)
    else:
        credential_exist = False

    if stack_exist:
        if not credential_exist and not credential_received:
            username, password = _request_dockerhub_credential(ctx=ctx)
            dockerhub.store_credential(manifest=manifest, username=username, password=password)
            credential_exist = True
        elif credential_received:
            dockerhub.store_credential(
                manifest=manifest,
                username=cast(str, username),
                password=cast(str, password),
            )
            credential_exist = True
    else:
        manifest.deploy_id = uuid.uuid4().hex[:6]
        if not credential_received:
            username, password = _request_dockerhub_credential(ctx=ctx)
            credential_exist = False

    ctx.progress(5)
    _logger.debug("manifest.deploy_id: %s", manifest.deploy_id)
    template_filename = toolkit.synth(manifest=manifest)
    cfn.deploy_template(
        manifest=manifest, stack_name=manifest.toolkit_stack_name, filename=template_filename, env_tag=manifest.env_tag
    )
    sleep(15)  # Avoiding eventual consistency issues
    manifest.fetch_toolkit_data()

    if credential_exist is False:
        dockerhub.store_credential(
            manifest=manifest,
            username=cast(str, username),
            password=cast(str, password),
        )


def deploy_foundation(
    filename: str,
    debug: bool,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    with MessagesContext("Deploying", debug=debug) as ctx:
        ctx.progress(2)

        manifest = Manifest(filename=filename, env=None, region=None)
        manifest.fillup()
        ctx.info(f"Manifest loaded: {filename}")
        ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        ctx.progress(3)

        _logger.debug("Inspecting possible manifest changes...")
        changes: Changeset = extract_changeset(manifest=manifest, ctx=ctx)
        _logger.debug(f"Changeset: {changes.asdict()}")
        ctx.progress(4)
        deploy_toolkit(
            manifest=manifest,
            username=username,
            password=password,
            ctx=ctx,
        )
        ctx.info("Toolkit deployed")
        ctx.progress(10)

        bundle_path = bundle.generate_bundle(
            command_name="deploy",
            manifest=manifest,
            changeset=changes,
        )
        ctx.progress(15)
        buildspec = codebuild.generate_spec(
            manifest=manifest,
            plugins=True,
            cmds_build=["orbit remote --command deploy_foundation ./conf/manifest.yaml"],
            changeset=changes,
        )
        remote.run(
            command_name="deploy_foundation",
            manifest=manifest,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=ctx.progress_bar_callback,
            timeout=90,
        )
        ctx.info("Orbit Foundation deployed")
        ctx.progress(100)


def deploy_env(
    filename: str,
    skip_images: bool,
    env_only: bool,
    debug: bool,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    with MessagesContext("Deploying", debug=debug) as ctx:
        ctx.progress(2)

        manifest = Manifest(filename=filename, env=None, region=None)
        manifest.fillup()
        ctx.info(f"Manifest loaded: {filename}")
        ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        ctx.progress(3)

        _logger.debug("Inspecting possible manifest changes...")
        changes: Changeset = extract_changeset(manifest=manifest, ctx=ctx)
        _logger.debug(f"Changeset: {changes.asdict()}")
        ctx.progress(4)

        plugins.PLUGINS_REGISTRIES.load_plugins(
            manifest=manifest,
            ctx=ctx,
            plugin_changesets=changes.plugin_changesets,
            teams_changeset=changes.teams_changeset,
        )
        ctx.progress(5)

        deploy_toolkit(
            manifest=manifest,
            username=username,
            password=password,
            ctx=ctx,
        )
        ctx.info("Toolkit deployed")
        ctx.progress(10)

        bundle_path = bundle.generate_bundle(
            command_name="deploy",
            manifest=manifest,
            dirs=_get_images_dirs(manifest=manifest, skip_images=skip_images),
            changeset=changes,
        )
        ctx.progress(15)
        skip_images_remote_flag: str = "skip-images" if skip_images else "no-skip-images"
        env_only_flag: str = "env-stacks" if env_only else "all-stacks"
        buildspec = codebuild.generate_spec(
            manifest=manifest,
            plugins=True,
            cmds_build=[
                f"orbit remote --command deploy ./conf/manifest.yaml {skip_images_remote_flag} {env_only_flag}"
            ],
            changeset=changes,
        )
        remote.run(
            command_name="deploy",
            manifest=manifest,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=ctx.progress_bar_callback,
            timeout=90,
        )
        ctx.info("Orbit Workbench deployed")
        ctx.progress(98)

        # if manifest.demo and cfn.does_stack_exist(manifest=manifest, stack_name=manifest.demo_stack_name):
        #     manifest.fetch_demo_data()
        #     ctx.info(f"Manifest updated: {filename}")
        # ctx.progress(99)

        if manifest.cognito_users_urls:
            ctx.tip(f"Add users: {stylize(manifest.cognito_users_urls, underline=True)}")
        else:
            RuntimeError("Cognito Users URL not found.")
        if manifest.landing_page_url:
            ctx.tip(f"Access Orbit Workbench: {stylize(manifest.landing_page_url, underline=True)}")
        else:
            RuntimeError("Landing Page URL not found.")
        ctx.progress(100)


def _deploy_image(env: str, dir: str, name: str, script: Optional[str], region: Optional[str], debug: bool) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as ctx:
        manifest = Manifest(filename=None, env=env, region=region)

        if cfn.does_stack_exist(manifest=manifest, stack_name=f"orbit-{manifest.name}") is False:
            ctx.error("Please, deploy your environment before deploy any addicional docker image")
            return

        _logger.debug("Inspecting possible manifest changes...")
        changes: Changeset = extract_changeset(manifest=manifest, ctx=ctx)
        _logger.debug(f"Changeset: {changes.asdict()}")
        ctx.progress(2)

        plugins.PLUGINS_REGISTRIES.load_plugins(
            manifest=manifest,
            ctx=ctx,
            plugin_changesets=changes.plugin_changesets,
            teams_changeset=changes.teams_changeset,
        )
        ctx.progress(3)

        bundle_path = bundle.generate_bundle(
            command_name=f"deploy_image-{name}", manifest=manifest, dirs=[(dir, name)], changeset=changes
        )
        ctx.progress(4)
        script_str = "" if script is None else script
        buildspec = codebuild.generate_spec(
            manifest=manifest,
            plugins=True,
            cmds_build=[f"orbit remote --command _deploy_image {env} {name} {script_str}"],
            changeset=changes,
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
        address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com/orbit-{manifest.name}-{name}"
        ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        ctx.progress(100)
