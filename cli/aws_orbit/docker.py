import logging
import os
from typing import TYPE_CHECKING, List, Optional

from aws_orbit import dockerhub, exceptions, sh, utils
from aws_orbit.services import ecr

if TYPE_CHECKING:
    from aws_orbit.manifest import Manifest

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


def login_ecr_only(manifest: "Manifest", account_id: Optional[str] = None, region: Optional[str] = None) -> None:
    if account_id is None:
        account_id = manifest.account_id
    if region is None:
        region = manifest.region
    username, password = ecr.get_credential(manifest=manifest, region=region)
    ecr_address = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    sh.run(
        f"docker login --username {username} --password {password} {ecr_address}",
        hide_cmd=True,
    )
    _logger.debug("ECR logged in (%s / %s).", account_id, region)


def dockerhub_pull(name: str, tag: str = "latest") -> None:
    sh.run(f"docker pull {name}:{tag}")


def ecr_pull(manifest: "Manifest", name: str, tag: str = "latest") -> None:
    if name.startswith("public.ecr.aws"):
        repository = f"{name}"
    else:
        repository = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com/{name}"
    sh.run(f"docker pull {repository}:{tag}")


def ecr_pull_external(manifest: "Manifest", repository: str, tag: str = "latest") -> None:
    parts: List[str] = repository.split(".")
    if len(parts) < 6:
        raise ValueError(f"Invalid External ECR Repository: {repository}")
    external_account_id: str = parts[0]
    external_region: str = parts[3]
    login_ecr_only(manifest=manifest, account_id=external_account_id, region=external_region)
    sh.run(f"docker pull {repository}:{tag}")


def tag_image(manifest: "Manifest", remote_name: str, remote_source: str, name: str, tag: str = "latest") -> None:
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    if remote_source == "ecr":
        remote_name = f"{ecr_address}/{remote_name}"
    sh.run(f"docker tag {remote_name}:{tag} {ecr_address}/{name}:{tag}")


def build(
    manifest: "Manifest", dir: str, name: str, tag: str = "latest", use_cache: bool = True, pull: bool = False
) -> None:
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    repo_address = f"{ecr_address}/{name}:{tag}"
    cache_str: str = ""
    pull_str: str = "--pull" if pull else ""
    if use_cache:
        try:
            ecr_pull(manifest=manifest, name=name, tag=tag)
            cache_str = f"--cache-from {repo_address}"
        except exceptions.FailedShellCommand:
            _logger.debug(f"Docker cache not found at ECR {name}:{tag}")
    sh.run(f"docker build {pull_str} {cache_str} --tag {name} .", cwd=dir)


def push(manifest: "Manifest", name: str, tag: str = "latest") -> None:
    ecr_address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com"
    repo_address = f"{ecr_address}/{name}:{tag}"
    sh.run(f"docker push {repo_address}")


def update_docker_file(manifest: "Manifest", dir: str) -> None:
    _logger.debug("Docker directory before building: %s", os.path.abspath(dir))
    utils.print_dir(dir)
    docker_file = os.path.join(dir, "Dockerfile")
    if os.path.exists(docker_file):
        _logger.info("Building DockerFile %s", docker_file)
        jupyter_user_base = (
            f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com/orbit-{manifest.name}-jupyter-user"
        )
        jupyter_user_spark_base = (
            f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com/"
            f"orbit-{manifest.name}-jupyter-user-spark"
        )
        with open(docker_file, "r") as file:
            content: str = file.read()
        content = utils.resolve_parameters(
            content,
            dict(
                region=manifest.region,
                account=manifest.account_id,
                env=manifest.name,
                jupyter_user_base=jupyter_user_base,
                jupyter_user_spark_base=jupyter_user_spark_base,
            ),
        )
        with open(docker_file, "w") as file:
            file.write(content)


def deploy_image_from_source(
    manifest: "Manifest",
    dir: str,
    name: str,
    tag: str = "latest",
    use_cache: bool = True,
) -> None:
    _logger.debug("Building docker image from %s", os.path.abspath(dir))
    update_docker_file(manifest=manifest, dir=dir)
    build(manifest=manifest, dir=dir, name=name, tag=tag, use_cache=use_cache, pull=True)
    _logger.debug("Docker Image built")
    tag_image(manifest=manifest, remote_name=name, remote_source="local", name=name, tag=tag)
    _logger.debug("Docker Image tagged")
    push(manifest=manifest, name=name, tag=tag)
    _logger.debug("Docker Image pushed")


def replicate_image(
    manifest: "Manifest",
    deployed_name: str,
    image_name: str,
) -> None:
    _logger.debug("Logged in")
    _logger.debug(f"Manifest: {vars(manifest)}")

    source = manifest.images[image_name]["source"]
    source_repository = manifest.images[image_name]["repository"]
    source_version = manifest.images[image_name]["version"]
    if source == "dockerhub":
        dockerhub_pull(name=source_repository, tag=source_version)
        _logger.debug("Pulled DockerHub Image")
    elif source == "ecr":
        ecr_pull(manifest=manifest, name=source_repository, tag=source_version)
        _logger.debug("Pulled ECR Image")
    elif source == "ecr-external":
        ecr_pull_external(manifest=manifest, repository=source_repository, tag=source_version)
        _logger.debug("Pulled external ECR Image")
    else:
        e = ValueError(f"Invalid Image Source: {source}. Valid values are: code, dockerhub, ecr")
        _logger.error(e)
        raise e

    tag_image(
        manifest=manifest, remote_name=source_repository, remote_source=source, name=deployed_name, tag=source_version
    )
    push(manifest=manifest, name=deployed_name, tag=source_version)
