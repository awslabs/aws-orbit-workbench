import logging
import os
from typing import TYPE_CHECKING, List, Optional

from aws_orbit import dockerhub, exceptions, sh, utils
from aws_orbit.services import ecr

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def login(context: "Context") -> None:
    username, password = dockerhub.get_credential(context=context)
    sh.run(f"docker login --username {username} --password {password}", hide_cmd=True)
    _logger.debug("DockerHub logged in.")
    username, password = ecr.get_credential()
    ecr_address = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com"
    sh.run(
        f"docker login --username {username} --password {password} {ecr_address}",
        hide_cmd=True,
    )
    _logger.debug("ECR logged in.")


def login_ecr_only(context: "Context", account_id: Optional[str] = None, region: Optional[str] = None) -> None:
    if account_id is None:
        account_id = context.account_id
    if region is None:
        region = context.region
    username, password = ecr.get_credential(region=region)
    ecr_address = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    sh.run(
        f"docker login --username {username} --password {password} {ecr_address}",
        hide_cmd=True,
    )
    _logger.debug("ECR logged in (%s / %s).", account_id, region)


def dockerhub_pull(name: str, tag: str = "latest") -> None:
    sh.run(f"docker pull {name}:{tag}")


def ecr_pull(context: "Context", name: str, tag: str = "latest") -> None:
    if name.startswith("public.ecr.aws"):
        repository = name
    else:
        repository = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/{name}"
    sh.run(f"docker pull {repository}:{tag}")


def ecr_pull_external(context: "Context", repository: str, tag: str = "latest") -> None:
    parts: List[str] = repository.split(".")
    if len(parts) < 6:
        raise ValueError(f"Invalid External ECR Repository: {repository}")
    external_account_id: str = parts[0]
    external_region: str = parts[3]
    login_ecr_only(context=context, account_id=external_account_id, region=external_region)
    sh.run(f"docker pull {repository}:{tag}")


def tag_image(context: "Context", remote_name: str, remote_source: str, name: str, tag: str = "latest") -> None:
    ecr_address = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com"
    if remote_source == "ecr" and not remote_name.startswith("public.ecr.aws"):
        remote_name = f"{ecr_address}/{remote_name}"
    sh.run(f"docker tag {remote_name}:{tag} {ecr_address}/{name}:{tag}")


def build(
    context: "Context",
    dir: str,
    name: str,
    tag: str = "latest",
    use_cache: bool = True,
    pull: bool = False,
    build_args: Optional[List[str]] = None,
) -> None:
    ecr_address = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com"
    repo_address = f"{ecr_address}/{name}:{tag}"
    cache_str: str = ""
    pull_str: str = "--pull" if pull else ""
    build_args_str = " ".join([f"--build-arg {ba}" for ba in build_args]) if build_args else ""
    if use_cache:
        try:
            ecr_pull(context=context, name=name, tag=tag)
            cache_str = f"--cache-from {repo_address}"
        except exceptions.FailedShellCommand:
            _logger.debug(f"Docker cache not found at ECR {name}:{tag}")
    sh.run(f"docker build {pull_str} {cache_str} {build_args_str} --tag {name} .", cwd=dir)


def push(context: "Context", name: str, tag: str = "latest") -> None:
    ecr_address = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com"
    repo_address = f"{ecr_address}/{name}:{tag}"
    sh.run(f"docker push {repo_address}")


def update_docker_file(context: "Context", dir: str) -> None:
    _logger.debug("Docker directory before building: %s", os.path.abspath(dir))
    utils.print_dir(dir)
    docker_file = os.path.join(dir, "Dockerfile")
    if os.path.exists(docker_file):
        _logger.info("Building DockerFile %s", docker_file)
        jupyter_user_base = (
            f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}-jupyter-user"
        )

        with open(docker_file, "r") as file:
            content: str = file.read()
        content = utils.resolve_parameters(
            content,
            dict(
                region=context.region,
                account=context.account_id,
                env=context.name,
                jupyter_user_base=jupyter_user_base,
            ),
        )
        with open(docker_file, "w") as file:
            file.write(content)


def deploy_image_from_source(
    context: "Context",
    dir: str,
    name: str,
    tag: str = "latest",
    use_cache: bool = True,
    build_args: Optional[List[str]] = None,
) -> None:
    _logger.debug("Adding CodeArtifact login to build environment, used by Dockerfile")
    if context.codeartifact_domain and context.codeartifact_repository:
        ca_domain: str = context.codeartifact_domain
        ca_repo: str = context.codeartifact_repository
        sh.run(f"aws codeartifact login --tool pip --domain {ca_domain} --repository {ca_repo}")
        sh.run(f"cp /root/.config/pip/pip.conf ./{dir}/")
    build_args = [] if build_args is None else build_args
    _logger.debug("Building docker image from %s", os.path.abspath(dir))
    update_docker_file(context=context, dir=dir)
    build(context=context, dir=dir, name=name, tag=tag, use_cache=use_cache, pull=True, build_args=build_args)
    _logger.debug("Docker Image built")
    tag_image(context=context, remote_name=name, remote_source="local", name=name, tag=tag)
    _logger.debug("Docker Image tagged")
    push(context=context, name=name, tag=tag)
    _logger.debug("Docker Image pushed")


def replicate_image(
    context: "Context",
    deployed_name: str,
    image_name: str,
) -> None:
    _logger.debug("Logged in")
    _logger.debug(f"Context: {vars(context)}")

    attr_name: str = image_name.replace("-", "_")
    source = getattr(context.images, attr_name).source
    source_repository = getattr(context.images, attr_name).repository
    source_version = getattr(context.images, attr_name).version
    if source == "dockerhub":
        dockerhub_pull(name=source_repository, tag=source_version)
        _logger.debug("Pulled DockerHub Image")
    elif source == "ecr":
        ecr_pull(context=context, name=source_repository, tag=source_version)
        _logger.debug("Pulled ECR Image")
    elif source == "ecr-external":
        ecr_pull_external(context=context, repository=source_repository, tag=source_version)
        _logger.debug("Pulled external ECR Image")
    else:
        e = ValueError(f"Invalid Image Source: {source}. Valid values are: code, dockerhub, ecr")
        _logger.error(e)
        raise e

    tag_image(
        context=context, remote_name=source_repository, remote_source=source, name=deployed_name, tag=source_version
    )
    push(context=context, name=deployed_name, tag=source_version)
