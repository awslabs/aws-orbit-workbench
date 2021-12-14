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
from typing import List, Optional, TypeVar

from aws_orbit import exceptions, sh, utils
from aws_orbit.models.context import Context, FoundationContext
from aws_orbit.services import ecr

_logger: logging.Logger = logging.getLogger(__name__)


T = TypeVar("T")


def login(context: T) -> None:
    # leaving this method to support legacy build process
    if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
        raise ValueError("Unknown 'context' Type")

    username, password = ecr.get_credential()
    ecr_address = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com"
    sh.run(
        f"docker login --username {username} --password {password} {ecr_address}",
        hide_cmd=True,
    )
    _logger.debug("ECR logged in.")


def login_v2(account_id: str, region: str) -> None:
    username, password = ecr.get_credential()
    ecr_address = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    sh.run(
        f"docker login --username {username} --password {password} {ecr_address}",
        hide_cmd=True,
    )
    _logger.debug("ECR logged in.")


def ecr_pull(name: str, tag: str = "latest") -> None:
    sh.run(f"docker pull {name}:{tag}")


def tag_image(account_id: str, region: str, name: str, tag: str = "latest") -> None:
    ecr_address = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    remote_name = f"{ecr_address}/{name}"
    _logger.debug(f"Tagging {name}:{tag} as {remote_name}:{tag}")
    sh.run(f"docker tag {name}:{tag} {remote_name}:{tag}")


def build(
    account_id: str,
    region: str,
    dir: str,
    name: str,
    tag: str = "latest",
    use_cache: bool = True,
    pull: bool = False,
    build_args: Optional[List[str]] = None,
) -> None:
    ecr_address = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    repo_address = f"{ecr_address}/{name}"
    repo_address_tag = f"{repo_address}:{tag}"
    cache_str: str = ""
    pull_str: str = "--pull" if pull else ""
    build_args_str = " ".join([f"--build-arg {ba}" for ba in build_args]) if build_args else ""
    if use_cache:
        try:
            ecr_pull(name=repo_address, tag=tag)
            cache_str = f"--cache-from {repo_address_tag}"
        except exceptions.FailedShellCommand:
            _logger.debug(f"Docker cache not found at ECR {name}:{tag}")
    sh.run(f"docker build {pull_str} {cache_str} {build_args_str} --tag {name}:{tag} .", cwd=dir)


def push(account_id: str, region: str, name: str, tag: str = "latest") -> None:
    ecr_address = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    repo_address = f"{ecr_address}/{name}:{tag}"
    _logger.debug(f"Pushing {repo_address}")
    sh.run(f"docker push {repo_address}")


def update_docker_file(account_id: str, region: str, env: str, tag: str, dir: str) -> None:
    _logger.debug("Docker directory before building: %s", os.path.abspath(dir))
    utils.print_dir(dir)
    docker_file = os.path.join(dir, "Dockerfile")
    if os.path.exists(docker_file):
        _logger.info("Building DockerFile %s", docker_file)
        jupyter_user_base = f"{account_id}.dkr.ecr.{region}.amazonaws.com/orbit-{env}/jupyter-user:{tag}"
        _logger.debug(f"update_docker_file: jupyter_user_base =  {jupyter_user_base}")
        with open(docker_file, "r") as file:
            content: str = file.read()
        content = utils.resolve_parameters(
            content,
            dict(
                region=region,
                account=account_id,
                env=env,
                jupyter_user_base=jupyter_user_base,
            ),
        )
        with open(docker_file, "w") as file:
            file.write(content)


def deploy_image_from_source(
    dir: str,
    name: str,
    env: str,
    tag: str = "latest",
    use_cache: bool = True,
    build_args: Optional[List[str]] = None,
) -> None:
    _logger.debug(f"deploy_image_from_source {dir} {name} {env} {tag} {build_args}")
    if not os.path.exists(dir):
        bundle_dir = os.path.join("bundle", dir)
        if os.path.exists(bundle_dir):
            dir = bundle_dir
    account_id = utils.get_account_id()
    region = utils.get_region()
    build_args = [] if build_args is None else build_args
    _logger.debug("Building docker image from %s", os.path.abspath(dir))
    sh.run(cmd="docker system prune --all --force --volumes")
    update_docker_file(account_id=account_id, region=region, env=env, tag=tag, dir=dir)
    build(
        account_id=account_id,
        region=region,
        dir=dir,
        name=name,
        tag=tag,
        use_cache=use_cache,
        pull=True,
        build_args=build_args,
    )
    _logger.debug("Docker Image built")
    tag_image(account_id=account_id, region=region, name=name, tag=tag)
    _logger.debug("Docker Image tagged")
    push(account_id=account_id, region=region, name=name, tag=tag)
    _logger.debug("Docker Image pushed")
