import logging
from typing import Dict, List, Optional

import click

from aws_orbit import utils
from aws_orbit.manifest import Manifest
from aws_orbit.messages import print_list, stylize

_logger: logging.Logger = logging.getLogger(__name__)


def _fetch_repo_uri(names: List[str], manifest: Manifest) -> Dict[str, str]:
    names = [f"orbit-{manifest.name}-{x}" for x in names]
    ret: Dict[str, str] = {x: "" for x in names}
    client = manifest.boto3_client("ecr")
    paginator = client.get_paginator("describe_repositories")
    for page in paginator.paginate(repositoryNames=names):
        for repo in page["repositories"]:
            ret[repo["repositoryName"]] = repo["repositoryUri"]
    ret = {k.replace(f"orbit-{manifest.name}-", ""): v for k, v in ret.items()}
    return ret


def list_images(env: str, region: Optional[str]) -> None:
    manifest: Manifest = Manifest(filename=None, env=env, region=region)
    names = utils.extract_images_names(manifest=manifest)
    _logger.debug("names: %s", names)
    if names:
        uris = _fetch_repo_uri(names=names, manifest=manifest)
        print_list(
            tittle=f"Available docker images into the {stylize(manifest.name)} env:",
            items=[f"{k} {stylize(':')} {v}" for k, v in uris.items()],
        )
    else:
        click.echo(f"Thre is no docker images into the {stylize(manifest.name)} env.")


def list_env(variable: str) -> None:
    ssm = utils.boto3_client("ssm")
    params = ssm.get_parameters_by_path(Path="/orbit", Recursive=True)["Parameters"]

    _logger.debug(f"ssm /orbit parameters found {params}")

    env_info: Dict[str, str] = {}
    for p in params:
        if not p["Name"].endswith("manifest") or "teams" in p["Name"]:
            continue
        env_name = p["Name"].split("/")[2]
        _logger.debug(f"found env: {env_name}")
        manifest: Manifest = Manifest(filename=None, env=env_name, region=None)
        manifest.fillup()
        teams_list: str = ",".join([x.name for x in manifest.teams])
        if variable == "landing-page":
            print(manifest.landing_page_url)
            return
        elif variable == "toolkitbucket":
            print(manifest.toolkit_s3_bucket)
            return
        elif variable == "teams":
            print(f"[{teams_list}]")
            return
        elif variable == "all":
            if hasattr(manifest, "teams") and len(manifest.teams) > 0:
                env_info[
                    env_name
                ] = f"URL={manifest.landing_page_url}, Teams=[{teams_list}], ToolkitBucket={manifest.toolkit_s3_bucket}"
            else:
                env_info[env_name] = f"URL={manifest.landing_page_url}, No Teams Defined."
            if len(env_info) == 0:
                click.echo("There are no Orbit environments available")
                return

            print_list(
                tittle="Available Orbit environments:",
                items=[f"Name={k}{stylize(',')}{v}" for k, v in env_info.items()],
            )
        else:
            raise Exception(f"Unknown --variable option {variable}")
