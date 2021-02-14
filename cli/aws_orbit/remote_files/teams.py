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
from typing import TYPE_CHECKING, Iterator, List, Optional, cast

import boto3

from aws_orbit import ORBIT_CLI_ROOT, cdk, docker, plugins, sh
from aws_orbit.models.context import create_team_context_from_manifest, dump_context_to_ssm
from aws_orbit.models.manifest import load_manifest_from_ssm
from aws_orbit.remote_files import eksctl, kubectl
from aws_orbit.services import cfn, ecr
from aws_orbit.utils import boto3_client

if TYPE_CHECKING:
    from aws_orbit.models.changeset import TeamsChangeset
    from aws_orbit.models.context import Context, TeamContext
    from aws_orbit.models.manifest import Manifest

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
    elif image_name == "jupyter-user-spark":
        base_image_cmd = f"FROM {team_context.base_spark_image_address}"
    else:
        raise Exception(f"The image {image_name} is not deployable to individual Teams.")

    _logger.debug("base_image_cmd: %s", base_image_cmd)
    cmds: List[str] = [base_image_cmd]
    for plugin in team_context.plugins:
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
    _logger.debug("cmds: %s", cmds)
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
    image_name: str = f"orbit-{context.name}-{team_context.name}"
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
                _logger.debug("Uploading s3://{context.toolkit.s3_bucket}/{key}")
                client.put_object(
                    Body=script_content.encode("utf-8"),
                    Bucket=context.toolkit.s3_bucket,
                    Key=key,
                )


def eval_removed_teams(context: "Context", teams_changeset: Optional["TeamsChangeset"]) -> None:
    if teams_changeset is None:
        return
    _logger.debug("Teams %s must be deleted.", teams_changeset.removed_teams_names)
    if teams_changeset.removed_teams_names:
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
    for name in teams_changeset.removed_teams_names:
        team_context: Optional["TeamContext"] = context.get_team_by_name(name=name)
        if team_context is None:
            raise RuntimeError(f"Team {name} not found!")
        _logger.debug("Destroying team %s", name)
        plugins.PLUGINS_REGISTRIES.destroy_team_plugins(context=context, team_context=team_context)
        kubectl.destroy_team(context=context, team_context=team_context)
        eksctl.destroy_team(context=context, team_context=team_context)
        destroy(context=context, team_context=team_context)
        _logger.debug("Team %s destroyed", name)
        context.remove_team_by_name(name=name)
        dump_context_to_ssm(context=context)


def deploy(context: "Context", teams_changeset: Optional["TeamsChangeset"]) -> None:
    manifest: Optional["Manifest"] = load_manifest_from_ssm(env_name=context.name)
    if manifest is None:
        raise ValueError("manifest is None!")
    eval_removed_teams(context=context, teams_changeset=teams_changeset)
    for team_manifest in manifest.teams:
        args = [context.name, team_manifest.name]
        cdk.deploy(
            context=context,
            stack_name=f"orbit-{manifest.name}-{team_manifest.name}",
            app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "team.py"),
            args=args,
        )
        team_context: Optional["TeamContext"] = context.get_team_by_name(name=team_manifest.name)
        if team_context:
            team_context.fetch_team_data()
        else:
            team_context = create_team_context_from_manifest(manifest=manifest, team_manifest=team_manifest)
            team_context.fetch_team_data()
            context.teams.append(team_context)
        dump_context_to_ssm(context=context)

    for team_context in context.teams:
        _deploy_team_image(context=context, team_context=team_context, image="jupyter-user")
        _deploy_team_image(context=context, team_context=team_context, image="jupyter-user-spark")
        _deploy_team_bootstrap(context=context, team_context=team_context)


def destroy(context: "Context", team_context: "TeamContext") -> None:
    _logger.debug("Stack name: %s", team_context.stack_name)
    if cfn.does_stack_exist(stack_name=context.toolkit.stack_name):
        try:
            ecr.delete_repo(repo=f"orbit-{context.name}-{team_context.name}")
        except Exception as ex:
            _logger.debug("Skipping Team ECR Repository deletion. Cause: %s", ex)
        try:
            ecr.delete_repo(repo=f"orbit-{context.name}-{team_context.name}-spark")
        except Exception as ex:
            _logger.debug("Skipping Team ECR Repository (Spark) deletion. Cause: %s", ex)
        if cfn.does_stack_exist(stack_name=team_context.stack_name):
            args: List[str] = [context.name, team_context.name]
            cdk.destroy(
                context=context,
                stack_name=team_context.stack_name,
                app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "team.py"),
                args=args,
            )


def destroy_all(context: "Context") -> None:
    for team_context in context.teams:
        destroy(context=context, team_context=team_context)
    context.teams = []
    dump_context_to_ssm(context=context)
