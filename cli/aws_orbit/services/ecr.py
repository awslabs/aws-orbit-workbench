import itertools
import logging
from base64 import b64decode
from typing import Any, Iterator, Optional, Tuple, cast

import boto3

from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def _chunks(iterable: Iterator[Any], size: int) -> Iterator[Any]:
    iterator = iter(iterable)
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, size - 1))


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
