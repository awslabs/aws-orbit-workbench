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
import time
from typing import Any, Dict, Iterator, List

import boto3

from datamaker_cli import plugins
from datamaker_cli.manifest import Manifest
from datamaker_cli.remote_files import cdk
from datamaker_cli.services import cfn, ecr

STACK_NAME = "datamaker-{env_name}"

_logger: logging.Logger = logging.getLogger(__name__)


def _filter_repos(page: Dict[str, Any], env_name: str) -> Iterator[str]:
    client = boto3.client("ecr")
    for repo in page["repositories"]:
        response: Dict[str, Any] = client.list_tags_for_resource(resourceArn=repo["repositoryArn"])
        for tag in response["tags"]:
            if tag["Key"] == "Env" and tag["Value"] == f"datamaker-{env_name}":
                yield repo["repositoryName"]


def _fetch_repos(env_name: str) -> Iterator[str]:
    client = boto3.client("ecr")
    paginator = client.get_paginator("describe_repositories")
    for page in paginator.paginate():
        for repo_name in _filter_repos(page=page, env_name=env_name):
            yield repo_name


def _ecr(env_name: str) -> None:
    for repo in _fetch_repos(env_name=env_name):
        ecr.delete_repo(repo=repo)


def _filter_filesystems(page: Dict[str, Any], env_name: str) -> Iterator[str]:
    for fs in page["FileSystems"]:
        for tag in fs["Tags"]:
            if tag["Key"] == "Env" and tag["Value"] == f"datamaker-{env_name}":
                yield fs["FileSystemId"]


def fetch_filesystems(env_name: str) -> Iterator[str]:
    client = boto3.client("efs")
    paginator = client.get_paginator("describe_file_systems")
    for page in paginator.paginate():
        for fs_id in _filter_filesystems(page=page, env_name=env_name):
            yield fs_id


def _fetch_targets(fs_id: str) -> Iterator[str]:
    client = boto3.client("efs")
    paginator = client.get_paginator("describe_mount_targets")
    for page in paginator.paginate(FileSystemId=fs_id):
        for target in page["MountTargets"]:
            yield target["MountTargetId"]


def _delete_targets(fs_id: str) -> None:
    client = boto3.client("efs")
    for target in _fetch_targets(fs_id=fs_id):
        try:
            client.delete_mount_target(MountTargetId=target)
        except client.exceptions.MountTargetNotFound:
            _logger.warning(f"Ignoring MountTargetId {target} deletion cause it does not exist anymore.")


def _efs_targets(env_name: str) -> List[str]:
    fs_ids: List[str] = []
    for fs_id in fetch_filesystems(env_name=env_name):
        fs_ids.append(fs_id)
        _delete_targets(fs_id=fs_id)
    return fs_ids


def _efs(fs_ids: List[str]) -> None:
    client = boto3.client("efs")
    for fs_id in fs_ids:
        while client.describe_file_systems(FileSystemId=fs_id)["FileSystems"][0]["NumberOfMountTargets"] > 0:
            time.sleep(1)
        client.delete_file_system(FileSystemId=fs_id)


def _cleanup_remaining_resources(env_name: str) -> None:
    _ecr(env_name=env_name)
    _efs(fs_ids=_efs_targets(env_name=env_name))


def deploy(manifest: Manifest, filename: str, add_images: List[str], remove_images: List[str]) -> None:
    stack_name = STACK_NAME.format(env_name=manifest.name)
    _logger.debug("Stack name: %s", stack_name)
    if not cfn.does_stack_exist(stack_name=stack_name) or manifest.dev:
        manifest.read_ssm()
        template_filename = cdk.env.synth(
            stack_name=stack_name,
            filename=filename,
            manifest=manifest,
            add_images=add_images,
            remove_images=remove_images,
        )
        _logger.debug("template_filename: %s", template_filename)
        cfn.deploy_template(stack_name=stack_name, filename=template_filename, env_tag=f"datamaker-{manifest.name}")
    for plugin in plugins.PLUGINS_REGISTRY.values():
        if plugin.deploy_env_hook is not None:
            plugin.deploy_env_hook(manifest)


def destroy(manifest: Manifest) -> None:
    stack_name = STACK_NAME.format(env_name=manifest.name)
    for plugin in plugins.PLUGINS_REGISTRY.values():
        if plugin.destroy_env_hook is not None:
            plugin.destroy_env_hook(manifest)
    _logger.debug("Stack name: %s", stack_name)
    if cfn.does_stack_exist(stack_name=stack_name):
        _cleanup_remaining_resources(env_name=manifest.name)
        cfn.destroy_stack(stack_name=stack_name)
