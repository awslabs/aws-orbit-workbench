import logging
from typing import Dict, List

import boto3
import click

from datamaker_cli.manifest import Manifest, read_manifest_file
from datamaker_cli.messages import print_list, stylize
from datamaker_cli.utils import extract_images_names

_logger: logging.Logger = logging.getLogger(__name__)


def _fetch_repo_uri(names: List[str], env_name: str) -> Dict[str, str]:
    names = [f"datamaker-{env_name}-{x}" for x in names]
    ret: Dict[str, str] = {x: "" for x in names}
    client = boto3.client("ecr")
    paginator = client.get_paginator("describe_repositories")
    for page in paginator.paginate(repositoryNames=names):
        for repo in page["repositories"]:
            ret[repo["repositoryName"]] = repo["repositoryUri"]
    ret = {k.replace(f"datamaker-{env_name}-", ""): v for k, v in ret.items()}
    return ret


def list_images(filename: str) -> None:
    manifest: Manifest = read_manifest_file(filename=filename)
    names = extract_images_names(env_name=manifest.name)
    _logger.debug("names: %s", names)
    if names:
        uris = _fetch_repo_uri(names=names, env_name=manifest.name)
        print_list(
            tittle=f"Available docker images into the {stylize(manifest.name)} env:",
            items=[f"{k} {stylize(':')} {v}" for k, v in uris.items()],
        )
    else:
        click.echo(f"Thre is no docker images into the {stylize(manifest.name)} env.")
