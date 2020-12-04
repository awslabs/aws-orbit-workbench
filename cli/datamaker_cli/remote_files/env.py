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
import time
from typing import Any, Dict, Iterator, List, Tuple

from datamaker_cli import DATAMAKER_CLI_ROOT, cdk, docker
from datamaker_cli.manifest import Manifest
from datamaker_cli.services import cfn, ecr

_logger: logging.Logger = logging.getLogger(__name__)


DEFAULT_IMAGES: List[str] = ["landing-page", "jupyter-hub", "jupyter-user"]
DEFAULT_ISOLATED_IMAGES: List[str] = ["aws-efs-csi-driver", "livenessprobe", "csi-node-driver-registrar"]


def _filter_repos(manifest: Manifest, page: Dict[str, Any]) -> Iterator[str]:
    client = manifest.boto3_client("ecr")
    for repo in page["repositories"]:
        response: Dict[str, Any] = client.list_tags_for_resource(resourceArn=repo["repositoryArn"])
        for tag in response["tags"]:
            if tag["Key"] == "Env" and tag["Value"] == f"datamaker-{manifest.name}":
                yield repo["repositoryName"]


def _fetch_repos(manifest: Manifest) -> Iterator[str]:
    client = manifest.boto3_client("ecr")
    paginator = client.get_paginator("describe_repositories")
    for page in paginator.paginate():
        for repo_name in _filter_repos(manifest=manifest, page=page):
            yield repo_name


def _ecr(manifest: Manifest) -> None:
    for repo in _fetch_repos(manifest=manifest):
        ecr.delete_repo(manifest=manifest, repo=repo)


def _filter_filesystems(page: Dict[str, Any], env_name: str) -> Iterator[str]:
    for fs in page["FileSystems"]:
        for tag in fs["Tags"]:
            if tag["Key"] == "Env" and tag["Value"] == f"datamaker-{env_name}":
                yield fs["FileSystemId"]


def fetch_filesystems(manifest: Manifest) -> Iterator[str]:
    client = manifest.boto3_client("efs")
    paginator = client.get_paginator("describe_file_systems")
    for page in paginator.paginate():
        for fs_id in _filter_filesystems(page=page, env_name=manifest.name):
            yield fs_id


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
            client.delete_mount_target(MountTargetId=target)
        except client.exceptions.MountTargetNotFound:
            _logger.warning(f"Ignoring MountTargetId {target} deletion cause it does not exist anymore.")


def _efs_targets(manifest: Manifest) -> List[str]:
    fs_ids: List[str] = []
    for fs_id in fetch_filesystems(manifest=manifest):
        fs_ids.append(fs_id)
        _delete_targets(manifest=manifest, fs_id=fs_id)
    return fs_ids


def _efs(manifest: Manifest, fs_ids: List[str]) -> None:
    client = manifest.boto3_client("efs")
    for fs_id in fs_ids:
        while client.describe_file_systems(FileSystemId=fs_id)["FileSystems"][0]["NumberOfMountTargets"] > 0:
            time.sleep(1)
        client.delete_file_system(FileSystemId=fs_id)


def _cleanup_remaining_resources(manifest: Manifest) -> None:
    _ecr(manifest=manifest)
    _efs(manifest=manifest, fs_ids=_efs_targets(manifest=manifest))


def _concat_images_into_args(manifest: Manifest, add_images: List[str], remove_images: List[str]) -> Tuple[str, str]:
    add_images += DEFAULT_IMAGES
    if manifest.internet_accessible is False:
        add_images += DEFAULT_ISOLATED_IMAGES
    add_images_str = ",".join(add_images) if add_images else "null"
    remove_images_str = ",".join(remove_images) if remove_images else "null"
    return add_images_str, remove_images_str


def deploy(manifest: Manifest, add_images: List[str], remove_images: List[str]) -> None:
    _logger.debug("Stack name: %s", manifest.env_stack_name)
    add_images_str, remove_images_str = _concat_images_into_args(
        manifest=manifest, add_images=add_images, remove_images=remove_images
    )
    cdk.deploy(
        manifest=manifest,
        stack_name=manifest.env_stack_name,
        app_filename=os.path.join(DATAMAKER_CLI_ROOT, "remote_files", "cdk", "env.py"),
        args=[manifest.filename, add_images_str, remove_images_str],
    )
    manifest.fetch_ssm()
    manifest.fetch_cognito_external_idp_data()


def destroy(manifest: Manifest) -> None:
    _logger.debug("Stack name: %s", manifest.env_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=manifest.env_stack_name):
        docker.login(manifest=manifest)
        _logger.debug("DockerHub and ECR Logged in")
        _cleanup_remaining_resources(manifest=manifest)
        add_images_str, remove_images_str = _concat_images_into_args(manifest=manifest, add_images=[], remove_images=[])
        cdk.destroy(
            manifest=manifest,
            stack_name=manifest.env_stack_name,
            app_filename=os.path.join(DATAMAKER_CLI_ROOT, "remote_files", "cdk", "env.py"),
            args=[manifest.filename, add_images_str, remove_images_str],
        )
