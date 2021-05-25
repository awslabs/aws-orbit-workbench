import itertools
import logging
from base64 import b64decode
from typing import Any, Dict, Iterator, List, Optional, Tuple, cast

import boto3

from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def _chunks(iterable: Iterator[Any], size: int) -> Iterator[Any]:
    iterator = iter(iterable)
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, size - 1))


def _filter_repos(env_name: str, page: Dict[str, Any]) -> Iterator[str]:
    client = boto3_client("ecr")
    for repo in page["repositories"]:
        if repo["repositoryName"].startswith(f"orbit-{env_name}/"):
            yield repo["repositoryName"]
        elif repo["repositoryName"].startswith(f"orbit-{env_name}-"):
            yield repo["repositoryName"]
        else:
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


def get_credential(region: Optional[str] = None) -> Tuple[str, str]:
    if region is None:
        ecr_client = boto3_client("ecr")
    else:
        _logger.debug("Creating custom boto3 session for region %s", region)
        ecr_client = boto3.Session(region_name=region).client("ecr")
    result = ecr_client.get_authorization_token()
    auth = result["authorizationData"][0]
    auth_token = b64decode(auth["authorizationToken"]).decode()
    return cast(Tuple[str, str], tuple(auth_token.split(sep=":", maxsplit=1)))


def fetch_images(repo: str) -> Iterator[str]:
    client = boto3_client("ecr")
    paginator = client.get_paginator("list_images")
    for page in paginator.paginate(repositoryName=repo):
        for image in page["imageIds"]:
            yield image["imageDigest"]


def delete_images(repo: str) -> None:
    client = boto3_client("ecr")
    for chunk in _chunks(iterable=fetch_images(repo=repo), size=100):
        client.batch_delete_image(repositoryName=repo, imageIds=[{"imageDigest": i} for i in chunk])


def delete_repo(repo: str) -> None:
    client = boto3_client("ecr")
    _logger.debug("Deleting Repository Images: %s", repo)
    delete_images(repo=repo)
    _logger.debug("Deleting Repository: %s", repo)
    client.delete_repository(repositoryName=repo, force=True)


def cleanup_remaining_repos(env_name: str) -> None:
    _logger.debug("Deleting any remaining ECR Repos")
    for repo in _fetch_repos(env_name=env_name):
        delete_repo(repo=repo)


def create_repository(repository_name: str, env_name: Optional[str] = None) -> None:
    client = boto3_client("ecr")
    params: Dict[str, Any] = {"repositoryName": repository_name}
    if env_name:
        params["tags"] = [{"Key": "Env", "Value": env_name}]
    response = client.create_repository(**params)
    if "repository" in response and "repositoryName" in response["repository"]:
        _logger.debug("ECR repository not exist, creating for %s", repository_name)
    else:
        _logger.error("ECR repository creation failed, response %s", response)
        raise RuntimeError(response)


def describe_repositories(repository_names: List[str]) -> List[Dict[str, Any]]:
    client = boto3_client("ecr")
    try:
        return cast(
            List[Dict[str, Any]], client.describe_repositories(repositoryNames=repository_names)["repositories"]
        )
    except client.exceptions.RepositoryNotFoundException:
        return []
