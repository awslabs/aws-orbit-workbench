import logging
from typing import TYPE_CHECKING, Dict, List, Optional

import click

from aws_orbit import utils
from aws_orbit.messages import print_list, stylize
from aws_orbit.models.context import Context, ContextSerDe
from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def _fetch_repo_uri(names: List[str], context: "Context") -> Dict[str, str]:
    names = [f"orbit-{context.name}-{x}" for x in names]
    ret: Dict[str, str] = {x: "" for x in names}
    client = boto3_client("ecr")
    paginator = client.get_paginator("describe_repositories")
    for page in paginator.paginate(repositoryNames=names):
        for repo in page["repositories"]:
            ret[repo["repositoryName"]] = repo["repositoryUri"]
    ret = {k.replace(f"orbit-{context.name}-", ""): v for k, v in ret.items()}
    return ret


def list_images(env: str, region: Optional[str]) -> None:
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
    names = utils.extract_images_names(env_name=env)
    _logger.debug("names: %s", names)
    if names:
        uris = _fetch_repo_uri(names=names, context=context)
        print_list(
            tittle=f"Available docker images into the {stylize(context.name)} env:",
            items=[f"{k} {stylize(':')} {v}" for k, v in uris.items()],
        )
    else:
        click.echo(f"Thre is no docker images into the {stylize(context.name)} env.")


def list_env(variable: str) -> None:
    ssm = utils.boto3_client("ssm")
    params = ssm.get_parameters_by_path(Path="/orbit", Recursive=True)["Parameters"]

    env_info: Dict[str, str] = {}
    for p in params:
        if not p["Name"].endswith("context") or "teams" in p["Name"]:
            continue
        env_name = p["Name"].split("/")[2]
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
        _logger.debug(f"found env: {env_name}")
        teams_list: str = ",".join([x.name for x in context.teams])
        if variable == "landing-page":
            print(context.landing_page_url)
            return
        elif variable == "toolkitbucket":
            print(context.toolkit.s3_bucket)
            return
        elif variable == "teams":
            print(f"[{teams_list}]")
            return
        elif variable == "all":
            if len(context.teams) > 0:
                env_info[
                    env_name
                ] = f"URL={context.landing_page_url}, Teams=[{teams_list}], ToolkitBucket={context.toolkit.s3_bucket}"
            else:
                env_info[env_name] = f"URL={context.landing_page_url}, No Teams Defined."
            if len(env_info) == 0:
                click.echo("There are no Orbit environments available")
                return

            print_list(
                tittle="Available Orbit environments:",
                items=[f"Name={k}{stylize(',')}{v}" for k, v in env_info.items()],
            )
        else:
            raise Exception(f"Unknown --variable option {variable}")
