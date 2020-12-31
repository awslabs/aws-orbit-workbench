import logging
import time
from typing import TYPE_CHECKING, Any, Dict, Iterator, List

if TYPE_CHECKING:
    from aws_orbit.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def _filter_env_filesystems(page: Dict[str, Any], env_name: str) -> Iterator[str]:
    for fs in page["FileSystems"]:
        for tag in fs["Tags"]:
            if tag["Key"] == "Env" and tag["Value"] == f"orbit-{env_name}":
                yield fs["FileSystemId"]


def _filter_filesystems_by_tag(page: Dict[str, Any], key: str, value: str) -> Iterator[str]:
    for fs in page["FileSystems"]:
        for tag in fs["Tags"]:
            if tag["Key"] == key and tag["Value"] == value:
                yield fs["FileSystemId"]


def fetch_env_filesystems(manifest: "Manifest") -> Iterator[str]:
    client = manifest.boto3_client("efs")
    paginator = client.get_paginator("describe_file_systems")
    for page in paginator.paginate():
        for fs_id in _filter_env_filesystems(page=page, env_name=manifest.name):
            yield fs_id


def fetch_filesystems_by_tag(manifest: "Manifest", key: str, value: str) -> Iterator[str]:
    client = manifest.boto3_client("efs")
    paginator = client.get_paginator("describe_file_systems")
    for page in paginator.paginate():
        for fs_id in _filter_filesystems_by_tag(page=page, key=key, value=value):
            yield fs_id


def fetch_targets(manifest: "Manifest", fs_id: str) -> Iterator[str]:
    client = manifest.boto3_client("efs")
    paginator = client.get_paginator("describe_mount_targets")
    for page in paginator.paginate(FileSystemId=fs_id):
        for target in page["MountTargets"]:
            yield target["MountTargetId"]


def delete_targets(manifest: "Manifest", fs_id: str) -> None:
    client = manifest.boto3_client("efs")
    for target in fetch_targets(manifest=manifest, fs_id=fs_id):
        try:
            _logger.debug("Deleting fs target %s (%s)", target, fs_id)
            client.delete_mount_target(MountTargetId=target)
        except client.exceptions.MountTargetNotFound:
            _logger.warning("Ignoring MountTargetId %s deletion cause it does not exist anymore.", target)
    while client.describe_file_systems(FileSystemId=fs_id)["FileSystems"][0]["NumberOfMountTargets"] > 0:
        _logger.debug("Waiting FileSystemId %s be empty...", fs_id)
        time.sleep(3)


def delete_env_filesystems(manifest: "Manifest") -> List[str]:
    client = manifest.boto3_client("efs")
    fs_ids: List[str] = []
    for fs_id in fetch_env_filesystems(manifest=manifest):
        fs_ids.append(fs_id)
        delete_targets(manifest=manifest, fs_id=fs_id)
        _logger.debug("Deleting fs %s", fs_id)
        client.delete_file_system(FileSystemId=fs_id)
    return fs_ids


def delete_filesystems_by_tag(manifest: "Manifest", key: str, value: str) -> List[str]:
    client = manifest.boto3_client("efs")
    fs_ids: List[str] = []
    for fs_id in fetch_filesystems_by_tag(manifest=manifest, key=key, value=value):
        fs_ids.append(fs_id)
        delete_targets(manifest=manifest, fs_id=fs_id)
        client.delete_file_system(FileSystemId=fs_id)
    return fs_ids


def delete_filesystems_by_team(manifest: "Manifest", team_name: str) -> None:
    fs_name: str = f"orbit-{manifest.name}-{team_name}-fs"
    _logger.debug("fs_name: %s...", fs_name)
    delete_filesystems_by_tag(manifest=manifest, key="Name", value=fs_name)
