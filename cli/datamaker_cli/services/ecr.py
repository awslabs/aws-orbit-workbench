import itertools
from base64 import b64decode
from typing import Any, Iterator, Tuple, cast

import boto3


def _chunks(iterable: Iterator[Any], size: int) -> Iterator[Any]:
    iterator = iter(iterable)
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, size - 1))


def get_credential() -> Tuple[str, str]:
    ecr_client = boto3.client("ecr")
    result = ecr_client.get_authorization_token()
    auth = result["authorizationData"][0]
    auth_token = b64decode(auth["authorizationToken"]).decode()
    return cast(Tuple[str, str], tuple(auth_token.split(sep=":", maxsplit=1)))


def fetch_images(repo: str) -> Iterator[str]:
    client = boto3.client("ecr")
    paginator = client.get_paginator("list_images")
    for page in paginator.paginate(repositoryName=repo):
        for image in page["imageIds"]:
            yield image["imageDigest"]


def delete_images(repo: str) -> None:
    client = boto3.client("ecr")
    for chunk in _chunks(iterable=fetch_images(repo), size=100):
        client.batch_delete_image(repositoryName=repo, imageIds=[{"imageDigest": i} for i in chunk])


def delete_repo(repo: str) -> None:
    client = boto3.client("ecr")
    delete_images(repo=repo)
    client.delete_repository(repositoryName=repo, force=True)
