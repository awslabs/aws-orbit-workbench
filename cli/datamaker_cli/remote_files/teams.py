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

from datamaker_cli import DATAMAKER_CLI_ROOT, cdk, docker, plugins
from datamaker_cli.manifest import Manifest
from datamaker_cli.services import cfn, ecr, s3

if TYPE_CHECKING:
    from datamaker_cli.changeset import PluginChangeset
    from datamaker_cli.manifest.team import TeamManifest

_logger: logging.Logger = logging.getLogger(__name__)


def _fetch_targets(manifest: Manifest, fs_id: str) -> Iterator[str]:
    client = manifest.boto3_client("efs")
    paginator = client.get_paginator("describe_mount_targets")
    for page in paginator.paginate(FileSystemId=fs_id):
        for target in page["MountTargets"]:
            yield target["MountTargetId"]


def _delete_targets(manifest: Manifest, fs_id: str) -> None:
    client = manifest.boto3_client("efs")
    for target in _fetch_targets(manifest=manifest, fs_id=fs_id):
        try:
            _logger.debug(f"Deleting MountTargetId: {target}")
            client.delete_mount_target(MountTargetId=target)
        except client.exceptions.MountTargetNotFound:
            _logger.warning(f"Ignoring MountTargetId {target} deletion cause it does not exist anymore.")


def _create_dockerfile(manifest: "Manifest", team_manifest: "TeamManifest") -> str:
    base_image_cmd: str = f"FROM {team_manifest.base_image_address}"
    _logger.debug("base_image_cmd: %s", base_image_cmd)
    cmds: List[str] = [base_image_cmd]
    for plugin in team_manifest.plugins:
        hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
            manifest=manifest,
            team_name=team_manifest.name,
            plugin_name=plugin.name,
            hook_name="dockerfile_injection_hook",
        )
        if hook is not None:
            plugin_cmds = cast(Optional[List[str]], hook(manifest, team_manifest))
            if plugin_cmds is not None:
                cmds += [f"# Commands for {plugin.name} plugin"] + plugin_cmds
    _logger.debug("cmds: %s", cmds)
    outdir = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, team_manifest.name, "image")
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


def _deploy_team_image(manifest: "Manifest", team_manifest: "TeamManifest") -> None:
    image_dir: str = _create_dockerfile(manifest=manifest, team_manifest=team_manifest)
    image_name: str = f"datamaker-{manifest.name}-{team_manifest.name}"
    _logger.debug("Deploying the %s Docker image", image_name)
    docker.deploy_image_from_source(manifest=manifest, dir=image_dir, name=image_name)
    _logger.debug("Docker Image Deployed to ECR")


def _deploy_team_bootstrap(manifest: "Manifest", team_manifest: "TeamManifest") -> None:
    for plugin in team_manifest.plugins:
        hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
            manifest=manifest,
            team_name=team_manifest.name,
            plugin_name=plugin.name,
            hook_name="bootstrap_injection_hook",
        )
        if hook is not None:
            script_content: Optional[str] = cast(Optional[str], hook(manifest, team_manifest))
            if script_content is not None:
                client = boto3.client("s3")
                key: str = f"{team_manifest.bootstrap_s3_prefix}{plugin.name}.sh"
                _logger.debug("Uploading s3://{manifest.toolkit_s3_bucket}/{key}")
                client.put_object(
                    Body=script_content.encode("utf-8"),
                    Bucket=manifest.toolkit_s3_bucket,
                    Key=key,
                )


def deploy(manifest: "Manifest", changes: List["PluginChangeset"]) -> None:
    for team_manifest in manifest.teams:
        cdk.deploy(
            manifest=manifest,
            stack_name=team_manifest.stack_name,
            app_filename=os.path.join(DATAMAKER_CLI_ROOT, "remote_files", "cdk", "team.py"),
            args=[manifest.filename, team_manifest.name],
        )
        team_manifest.fetch_ssm()
        plugins.PLUGINS_REGISTRIES.deploy_team_plugins(manifest=manifest, team_manifest=team_manifest, changes=changes)
    for team_manifest in manifest.teams:
        _deploy_team_image(manifest=manifest, team_manifest=team_manifest)
        _deploy_team_bootstrap(manifest=manifest, team_manifest=team_manifest)


def destroy(manifest: "Manifest") -> None:
    for team_manifest in manifest.teams:
        _logger.debug("Stack name: %s", team_manifest.stack_name)
        if cfn.does_stack_exist(manifest=manifest, stack_name=manifest.toolkit_stack_name):
            plugins.PLUGINS_REGISTRIES.destroy_team_plugins(manifest=manifest, team_manifest=team_manifest)
            if team_manifest.scratch_bucket is not None:
                try:
                    s3.delete_bucket(manifest=manifest, bucket=team_manifest.scratch_bucket)
                except Exception as ex:
                    _logger.debug("Skipping Team Scratch Bucket deletion. Cause: %s", ex)
            if team_manifest.efs_id is not None:
                try:
                    _delete_targets(manifest=manifest, fs_id=team_manifest.efs_id)
                except Exception as ex:
                    _logger.debug("Skipping Team EFS Target deletion. Cause: %s", ex)
            try:
                ecr.delete_repo(manifest=manifest, repo=f"datamaker-{manifest.name}-{team_manifest.name}")
            except Exception as ex:
                _logger.debug("Skipping Team ECR Repository deletion. Cause: %s", ex)
            if cfn.does_stack_exist(manifest=manifest, stack_name=team_manifest.stack_name):
                cdk.destroy(
                    manifest=manifest,
                    stack_name=team_manifest.stack_name,
                    app_filename=os.path.join(DATAMAKER_CLI_ROOT, "remote_files", "cdk", "team.py"),
                    args=[manifest.filename, team_manifest.name],
                )
