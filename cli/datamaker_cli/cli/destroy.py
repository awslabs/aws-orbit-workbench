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

import concurrent.futures
import itertools
import logging
import time
from typing import Any, Dict, Iterator, List, cast

import boto3
import botocore.exceptions

from datamaker_cli import cdk, demo, eksctl, kubectl
from datamaker_cli.manifest import Manifest, read_manifest_file
from datamaker_cli.spinner import start_spinner
from datamaker_cli.utils import get_k8s_context

_logger: logging.Logger = logging.getLogger(__name__)


def _chunks(iterable: Iterator[Any], size: int) -> Iterator[Any]:
    iterator = iter(iterable)
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, size - 1))


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


def _fetch_images(repo: str) -> Iterator[str]:
    client = boto3.client("ecr")
    paginator = client.get_paginator("list_images")
    for page in paginator.paginate(repositoryName=repo):
        for image in page["imageIds"]:
            yield image["imageDigest"]


def _delete_images(repo: str) -> None:
    client = boto3.client("ecr")
    for chunk in _chunks(iterable=_fetch_images(repo), size=100):
        client.batch_delete_image(repositoryName=repo, imageIds=[{"imageDigest": i} for i in chunk])


def _ecr(env_name: str) -> None:
    client = boto3.client("ecr")
    for repo in _fetch_repos(env_name=env_name):
        _delete_images(repo=repo)
        client.delete_repository(repositoryName=repo, force=True)


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


def _network_interface(vpc_id: str) -> None:
    client = boto3.client("ec2")
    ec2 = boto3.resource("ec2")
    for i in client.describe_network_interfaces(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["NetworkInterfaces"]:
        try:
            network_interface = ec2.NetworkInterface(i["NetworkInterfaceId"])
            if "Interface for NAT Gateway" not in network_interface.description:
                if network_interface.attachment is not None and network_interface.attachment["Status"] == "attached":
                    network_interface.detach()
                    network_interface.reload()
                    while network_interface.attachment is None or network_interface.attachment["Status"] != "detached":
                        time.sleep(1)
                        network_interface.reload()
                    network_interface.delete()
        except botocore.exceptions.ClientError as ex:
            error: Dict[str, Any] = ex.response["Error"]
            if "is currently in use" not in error["Message"]:
                _logger.warning(f"Ignoring NetWorkInterface {i['NetworkInterfaceId']} because it stills in use.")
            if "does not exist" not in error["Message"]:
                _logger.warning(
                    f"Ignoring NetWorkInterface {i['NetworkInterfaceId']} because it does not exist anymore."
                )
            raise


def delete_sec_group(sec_group: str) -> None:
    ec2 = boto3.resource("ec2")
    try:
        sgroup = ec2.SecurityGroup(sec_group)
        if sgroup.ip_permissions:
            sgroup.revoke_ingress(IpPermissions=sgroup.ip_permissions)
        sgroup.delete()
    except botocore.exceptions.ClientError as ex:
        error: Dict[str, Any] = ex.response["Error"]
        if f"The security group '{sec_group}' does not exist" not in error["Message"]:
            raise


def _security_group(vpc_id: str) -> None:
    client = boto3.client("ec2")
    sec_groups: List[str] = [
        s["GroupId"]
        for s in client.describe_security_groups()["SecurityGroups"]
        if s["VpcId"] == vpc_id and s["GroupName"] != "default"
    ]
    if sec_groups:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(sec_groups)) as executor:
            list(executor.map(delete_sec_group, sec_groups))


def _cleanup_cdk_remaining_resources(env_name: str) -> None:
    with start_spinner(msg="Destroying remaining resources") as spinner:
        _ecr(env_name=env_name)
        _efs(fs_ids=_efs_targets(env_name=env_name))
        spinner.succeed()


def _cleanup_demo_remaining_dependencies(manifest: Manifest) -> None:
    with start_spinner(msg="Destroying DEMO remaining dependencies") as spinner:
        if manifest.vpc.vpc_id is None:
            manifest.read_ssm()
            vpc_id: str = cast(str, manifest.vpc.vpc_id)
        else:
            vpc_id = manifest.vpc.vpc_id
        _network_interface(vpc_id=vpc_id)
        _security_group(vpc_id=vpc_id)
        spinner.succeed()


def destroy(filename: str) -> None:
    manifest: Manifest = read_manifest_file(filename=filename)
    manifest.read_ssm()

    try:
        context = get_k8s_context(manifest=manifest)
        _logger.debug("kubectl context: %s", context)
        manifest = kubectl.destroy(manifest=manifest, filename=filename, context=context)
    except RuntimeError:
        _logger.warning("There is no kubectl context anymore.")
    manifest = eksctl.destroy(manifest=manifest, filename=filename)
    manifest = cdk.destroy(manifest=manifest)
    _cleanup_cdk_remaining_resources(env_name=manifest.name)
    if manifest.demo:
        _cleanup_demo_remaining_dependencies(manifest=manifest)
        manifest = demo.destroy(manifest=manifest)
