import logging
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


def tag_image(manifest: "Manifest", remote_name: str, remote_source: str, name: str, tag: str = "latest") -> None:
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    if remote_source == "ecr":
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


def deploy_dynamic_image(
    manifest: "Manifest",
    dir: str,
    name: str,
    tag: str = "latest",
    use_cache: bool = True,
) -> None:
    login(manifest=manifest)
    _logger.debug("Logged in")
    build(manifest=manifest, dir=dir, name=name, tag=tag, use_cache=use_cache)
    _logger.debug("Docker Image built")
    tag_image(manifest=manifest, remote_name=name, remote_source="local", name=name, tag=tag)
    _logger.debug("Docker Image tagged")
    push(manifest=manifest, name=name, tag=tag)
    _logger.debug("Docker Image pushed")


def deploy(
    manifest: "Manifest",
    dir: str,
    deployed_name: str,
    image_name: str,
    use_cache: bool = True,
) -> None:
    login(manifest=manifest)
    _logger.debug("Logged in")
    _logger.debug(f"Manifest: {vars(manifest)}")

    source = manifest.images[image_name]["source"]
    source_name = manifest.images[image_name]["repository"]
    source_version = manifest.images[image_name]["version"]
    if source == "source" or manifest.dev is True:
        build(manifest=manifest, dir=dir, name=deployed_name, tag=source_version, use_cache=use_cache)
        _logger.debug("Built from Source")
    if source == "dockerhub":
        dockerhub_pull(name=source_name, tag=source_version)
        _logger.debug("Pulled DockerHub Image")
    elif source == "ecr":
        ecr_pull(manifest=manifest, name=source_name, tag=source_version)
        _logger.debug("Pulled ECR Image")
    else:
        e = ValueError(f"Invalid Image Source: {source}. Valid values are: dockerhub, ecr")
        _logger.error(e)
        raise e

    tag_image(manifest=manifest, remote_name=source_name, remote_source=source, name=deployed_name, tag=source_version)
    push(manifest=manifest, name=deployed_name, tag=source_version)
