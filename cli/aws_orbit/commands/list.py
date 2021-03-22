#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import logging
from typing import Dict, List, Optional

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
    res = ssm.get_parameters_by_path(Path="/orbit", Recursive=True)
    env_info: Dict[str, str] = {}
    while True:
        params = res["Parameters"]
        for p in params:
            if not p["Name"].endswith("context") or "teams" in p["Name"]:
                continue
            env_name = p["Name"].split("/")[2]
            context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
            _logger.debug(f"found env: {env_name}")
            if context.k8_dashboard_url:
                k8_dashboard_url = context.k8_dashboard_url
            else:
                k8_dashboard_url = ""
            if len(context.teams) > 0:
                teams_list: str = ",".join([x.name for x in context.teams])
            else:
                teams_list = ""

            if variable == "landing-page":
                print(context.landing_page_url)
            elif variable == "toolkitbucket":
                print(context.toolkit.s3_bucket)
            elif variable == "teams":
                print(f"[{teams_list}]")
            elif variable == "all":
                env_info[env_name] = (
                    f"LandingPage={context.landing_page_url}, "
                    f"Teams=[{teams_list}], "
                    f"ToolkitBucket={context.toolkit.s3_bucket}"
                    f"K8Dashboard={k8_dashboard_url}"
                )
            else:
                raise Exception(f"Unknown --variable option {variable}")

        if "NextToken" in res:
            res = ssm.get_parameters_by_path(Path="/orbit", Recursive=True, NextToken=res["NextToken"])
        else:
            break
    if len(env_info) == 0:
        click.echo("There are no Orbit environments available")
        return
    else:
        print_list(
            tittle="Available Orbit environments:",
            items=[f"Name={k}{stylize(',')}{v}" for k, v in env_info.items()],
        )
