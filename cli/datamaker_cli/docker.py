import logging
import os
import re
from typing import TYPE_CHECKING

from datamaker_cli import dockerhub, exceptions, sh
from datamaker_cli.services import ecr

if TYPE_CHECKING:
    from datamaker_cli.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def login(manifest: "Manifest") -> None:
    username, password = dockerhub.get_credential(manifest)
    sh.run(f"docker login --username {username} --password {password}", hide_cmd=True)
    _logger.debug("DockerHub logged in.")
    username, password = ecr.get_credential(manifest=manifest)
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    sh.run(
        f"docker login --username {username} --password {password} {ecr_address}",
        hide_cmd=True,
    )
    _logger.debug("ECR logged in.")


def dockerhub_pull(name: str, tag: str = "latest") -> None:
    sh.run(f"docker pull {name}:{tag}")


def ecr_pull(manifest: "Manifest", name: str, tag: str = "latest") -> None:
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    sh.run(f"docker pull {ecr_address}/{name}:{tag}")


def tag_image(manifest: "Manifest", remote_name: str, name: str, tag: str = "latest") -> None:
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    if manifest.images_source == "ecr":
        remote_name = f"{ecr_address}/{remote_name}"
    sh.run(f"docker tag {remote_name}:{tag} {ecr_address}/{name}:{tag}")


def build(
    manifest: "Manifest",
    dir: str,
    name: str,
    tag: str = "latest",
    use_cache: bool = True,
) -> None:
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    repo_address = f"{ecr_address}/{name}:{tag}"
    cache_str: str = ""
    if use_cache:
        try:
            ecr_pull(manifest=manifest, name=name, tag=tag)
            cache_str = f"--cache-from {repo_address}"
        except exceptions.FailedShellCommand:
            _logger.debug(f"Docker cache not found at ECR {name}:{tag}")

    sh.run(f"docker build {cache_str} --tag {name} .", cwd=dir)


def push(manifest: "Manifest", name: str, tag: str = "latest") -> None:
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    repo_address = f"{ecr_address}/{name}:{tag}"
    sh.run(f"docker push {repo_address}")


def deploy(
    manifest: "Manifest",
    dir: str,
    name: str,
    tag: str = "latest",
    use_cache: bool = True,
) -> None:
    login(manifest=manifest)
    _logger.debug("Logged in")

    if manifest.image_source == "dockerhub":
        dockerhub_pull(name=manifest.images[name], tag=tag)
        _logger.debug("Pulled DockerHub Image")
    else:
        ecr_pull(manifest=manifest, name=manifest.images[name], tag=tag)
        _logger.debug("Pulled ECR Image")

    tag_image(manifest=manifest, remote_name=manifest.images[name], name=name, tag=tag)
    push(manifest=manifest, name=name, tag=tag)

