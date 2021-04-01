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
import shutil
from typing import Iterator, List, Optional, cast

import boto3

import aws_orbit
from aws_orbit import ORBIT_CLI_ROOT, cdk, docker, plugins
from aws_orbit.models.context import Context, ContextSerDe, TeamContext, create_team_context_from_manifest
from aws_orbit.models.manifest import Manifest, TeamManifest
from aws_orbit.services import cfn
from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def _fetch_targets(context: "Context", fs_id: str) -> Iterator[str]:
    client = boto3_client("efs")
    paginator = client.get_paginator("describe_mount_targets")
    for page in paginator.paginate(FileSystemId=fs_id):
        for target in page["MountTargets"]:
            yield target["MountTargetId"]


def _delete_targets(context: "Context", fs_id: str) -> None:
    client = boto3_client("efs")
    for target in _fetch_targets(context=context, fs_id=fs_id):
        try:
            _logger.debug(f"Deleting MountTargetId: {target}")
            client.delete_mount_target(MountTargetId=target)
        except client.exceptions.MountTargetNotFound:
            _logger.warning(f"Ignoring MountTargetId {target} deletion cause it does not exist anymore.")


def _create_dockerfile(context: "Context", team_context: "TeamContext", image_name: str) -> str:
    if image_name == "jupyter-user":
        base_image_cmd = f"FROM {team_context.base_image_address}"
    else:
        raise Exception(f"The image {image_name} is not deployable to individual Teams.")

    _logger.debug("base_image_cmd: %s", base_image_cmd)
    cmds: List[str] = [base_image_cmd]

    # Add CodeArtifact pip.conf
    cmds += ["USER root"]
    cmds += ["ADD pip.conf /etc/pip.conf"]

    for plugin in team_context.plugins:
        # Adding plugin modules to image via pip
        plugin_module_name = (plugin.module).replace("_", "-")
        cmds += [f"RUN pip install --upgrade aws-orbit-{plugin_module_name}=={aws_orbit.__version__}"]

        hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
            context=context,
            team_name=team_context.name,
            plugin_name=plugin.plugin_id,
            hook_name="dockerfile_injection_hook",
        )
        if hook is not None:
            plugin_cmds = cast(Optional[List[str]], hook(plugin.plugin_id, context, team_context, plugin.parameters))
            if plugin_cmds is not None:
                cmds += [f"# Commands for {plugin.plugin_id} plugin"] + plugin_cmds

    # Removing pip conf and setting to notebook user
    cmds += ["RUN rm /etc/pip.conf", "USER $NB_UID"]
    _logger.debug("Dockerfile cmds: %s", cmds)
    outdir = os.path.join(".orbit.out", context.name, team_context.name, "image")
    output_filename = os.path.join(outdir, "Dockerfile")
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)
    _logger.debug("Writing %s", output_filename)
    os.makedirs(outdir, exist_ok=True)
    content: str = "\n".join(cmds)
    _logger.debug("content:\n%s", content)
    with open(output_filename, "w") as file:
        file.write(content)
    return outdir


def _deploy_team_image(context: "Context", team_context: "TeamContext", image: str) -> None:
    image_dir: str = _create_dockerfile(context=context, team_context=team_context, image_name=image)
    image_name: str = f"orbit-{context.name}-{team_context.name}-{image}"
    _logger.debug("Deploying the %s Docker image", image_name)
    docker.deploy_image_from_source(context=context, dir=image_dir, name=image_name)
    _logger.debug("Docker Image Deployed to ECR (%s).", image_name)


def _deploy_team_bootstrap(context: "Context", team_context: "TeamContext") -> None:
    for plugin in team_context.plugins:
        hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
            context=context,
            team_name=team_context.name,
            plugin_name=plugin.plugin_id,
            hook_name="bootstrap_injection_hook",
        )
        if hook is not None:
            script_content: Optional[str] = cast(
                Optional[str], hook(plugin.plugin_id, context, team_context, plugin.parameters)
            )
            if script_content is not None:
                client = boto3.client("s3")
                key: str = f"{team_context.bootstrap_s3_prefix}{plugin.plugin_id}.sh"
                _logger.debug(f"Uploading s3://{context.toolkit.s3_bucket}/{key}")
                client.put_object(
                    Body=script_content.encode("utf-8"),
                    Bucket=context.toolkit.s3_bucket,
                    Key=key,
                )


def deploy_team(context: "Context", manifest: Manifest, team_manifest: TeamManifest) -> None:
    # Pull team spacific custom cfn plugin, trigger pre_hook
    team_context: Optional["TeamContext"] = create_team_context_from_manifest(
        manifest=manifest, team_manifest=team_manifest
    )
    _logger.debug(f"team_context={team_context}")
    if team_context:
        _logger.debug(f"team_context.plugins={team_context.plugins}")
        _logger.debug("Calling team pre_hook")
        for plugin in team_context.plugins:
            hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
                context=context,
                team_name=team_context.name,
                plugin_name=plugin.plugin_id,
                hook_name="pre_hook",
            )
            if hook is not None:
                _logger.debug(f"Found pre_hook for plugin_id {plugin}")
                hook(plugin.plugin_id, context, team_context, plugin.parameters)
        _logger.debug("End of pre_hook plugin execution")
    else:
        _logger.debug(f"Skipping pre_hook for unknown Team: {team_manifest.name}")

    args = [context.name, team_manifest.name]
    cdk.deploy(
        context=context,
        stack_name=f"orbit-{manifest.name}-{team_manifest.name}",
        app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "team.py"),
        args=args,
    )
    team_context = context.get_team_by_name(name=team_manifest.name)
    if team_context:
        team_context.fetch_team_data()
    else:
        team_context = create_team_context_from_manifest(manifest=manifest, team_manifest=team_manifest)
        team_context.fetch_team_data()
        context.teams.append(team_context)
    ContextSerDe.dump_context_to_ssm(context=context)


def destroy_team(context: "Context", team_context: "TeamContext") -> None:
    _logger.debug("Stack name: %s", team_context.stack_name)
    if cfn.does_stack_exist(stack_name=context.toolkit.stack_name):
        if cfn.does_stack_exist(stack_name=team_context.stack_name):
            args: List[str] = [context.name, team_context.name]
            cdk.destroy(
                context=context,
                stack_name=team_context.stack_name,
                app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "team.py"),
                args=args,
            )

        _logger.debug("Team specific post_hook execute to destroy the cfn resources")
        _logger.debug(f"team_context.plugins={team_context.plugins}")
        for plugin in team_context.plugins:
            _logger.debug(f"Checking post hook for plugin={plugin}")
            hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
                context=context,
                team_name=team_context.name,
                plugin_name=plugin.plugin_id,
                hook_name="post_hook",
            )
            if hook is not None:
                _logger.debug(f"Found post hook for team {team_context.name} plugin {plugin.plugin_id}")
                hook(plugin.plugin_id, context, team_context, plugin.parameters)


def destroy_all(context: "Context") -> None:
    for team_context in context.teams:
        destroy_team(context=context, team_context=team_context)
    context.teams = []
    ContextSerDe.dump_context_to_ssm(context=context)
