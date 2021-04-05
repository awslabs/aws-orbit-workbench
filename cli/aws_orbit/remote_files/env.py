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
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Tuple

from aws_orbit import ORBIT_CLI_ROOT, cdk, docker
from aws_orbit.services import cfn, ecr, iam, ssm
from aws_orbit.utils import boto3_client

if TYPE_CHECKING:
    from aws_orbit.models.changeset import ListChangeset
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)

DEFAULT_IMAGES: List[str] = ["landing-page", "jupyter-hub", "jupyter-user"]
DEFAULT_ISOLATED_IMAGES: List[str] = [
    "aws-efs-csi-driver",
    "livenessprobe",
    "csi-node-driver-registrar",
    "k8-dashboard",
    "k8-metrics-scraper",
    "k8-metrics-server",
    "cluster-autoscaler",
]


def _filter_repos(env_name: str, page: Dict[str, Any]) -> Iterator[str]:
    client = boto3_client("ecr")
    for repo in page["repositories"]:
        response: Dict[str, Any] = client.list_tags_for_resource(resourceArn=repo["repositoryArn"])
        for tag in response["tags"]:
            if tag["Key"] == "Env" and tag["Value"] == f"orbit-{env_name}":
                yield repo["repositoryName"]


def _fetch_repos(env_name: str) -> Iterator[str]:
    client = boto3_client("ecr")
    paginator = client.get_paginator("describe_repositories")
    for page in paginator.paginate():
        for repo_name in _filter_repos(env_name, page=page):
            yield repo_name


def _cleanup_remaining_resources(env_name: str) -> None:
    for repo in _fetch_repos(env_name=env_name):
        ecr.delete_repo(repo=repo)


def _concat_images_into_args(context: "Context", add_images: List[str], remove_images: List[str]) -> Tuple[str, str]:
    add_images += DEFAULT_IMAGES
    if context.networking.data.internet_accessible is False:
        add_images += DEFAULT_ISOLATED_IMAGES
    add_images_str = ",".join(add_images) if add_images else "null"
    remove_images_str = ",".join(remove_images) if remove_images else "null"
    return add_images_str, remove_images_str


def deploy(
    context: "Context",
    add_images: List[str],
    remove_images: List[str],
    eks_system_masters_roles_changes: Optional["ListChangeset"],
) -> None:
    _logger.debug("Stack name: %s", context.env_stack_name)

    if eks_system_masters_roles_changes and (
        eks_system_masters_roles_changes.added_values or eks_system_masters_roles_changes.removed_values
    ):
        iam.update_assume_role_roles(
            account_id=context.account_id,
            role_name=f"orbit-{context.name}-admin",
            roles_to_add=eks_system_masters_roles_changes.added_values,
            roles_to_remove=eks_system_masters_roles_changes.removed_values,
        )

    add_images_str, remove_images_str = _concat_images_into_args(
        context=context, add_images=add_images, remove_images=remove_images
    )
    args: List[str] = [context.name, add_images_str, remove_images_str]

    cdk.deploy(
        context=context,
        stack_name=context.env_stack_name,
        app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "env.py"),
        args=args,
    )
    context.fetch_env_data()


def destroy(context: "Context") -> None:
    _logger.debug("Stack name: %s", context.env_stack_name)
    if cfn.does_stack_exist(stack_name=context.env_stack_name):
        docker.login(context=context)
        _logger.debug("DockerHub and ECR Logged in")
        _cleanup_remaining_resources(env_name=context.name)
        add_images_str, remove_images_str = _concat_images_into_args(context=context, add_images=[], remove_images=[])
        args = [context.name, add_images_str, remove_images_str]
        cdk.destroy(
            context=context,
            stack_name=context.env_stack_name,
            app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "env.py"),
            args=args,
        )
        ssm.cleanup_context(env_name=context.name)
