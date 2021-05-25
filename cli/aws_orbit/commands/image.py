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

import json
import logging
import os
from typing import Any, Dict, List, Optional, cast

import botocore
from slugify import slugify

from aws_orbit import bundle, remote, utils
from aws_orbit.messages import MessagesContext, stylize
from aws_orbit.models.context import Context, ContextSerDe
from aws_orbit.services import cfn, codebuild

_logger: logging.Logger = logging.getLogger(__name__)
PROFILES_TYPE = List[Dict[str, Any]]


def read_user_profiles_ssm(env_name: str, team_name: str) -> PROFILES_TYPE:
    ssm_profile_name = f"/orbit/{env_name}/teams/{team_name}/user/profiles"
    _logger.debug("Trying to read profiles from SSM parameter (%s).", ssm_profile_name)
    client = utils.boto3_client(service_name="ssm")
    try:
        json_str: str = client.get_parameter(Name=ssm_profile_name)["Parameter"]["Value"]
    except botocore.errorfactory.ParameterNotFound:
        _logger.info("No team profile found, returning only default profiles")
        pass

    return cast(PROFILES_TYPE, json.loads(json_str))


def write_context_ssm(profiles: PROFILES_TYPE, env_name: str, team_name: str) -> None:
    ssm_profile_name = f"/orbit/{env_name}/teams/{team_name}/user/profiles"
    client = utils.boto3_client(service_name="ssm")
    _logger.debug("Writing team %s user profiles to SSM parameter.", team_name)
    json_str = str(json.dumps(obj=profiles, sort_keys=True))
    # resolve any parameters inside team context per context
    json_str = utils.resolve_parameters(
        json_str, dict(region=utils.get_region(), account=utils.get_account_id(), env=env_name, team=team_name)
    )
    client.put_parameter(
        Name=ssm_profile_name,
        Value=json_str,
        Overwrite=True,
        Tier="Intelligent-Tiering",
    )


def delete_profile(env: str, team: str, profile_name: str, debug: bool) -> None:
    with MessagesContext("Profile Deleted", debug=debug) as msg_ctx:
        msg_ctx.info("Retrieving existing profiles")
        profiles: List[Dict[str, Any]] = read_user_profiles_ssm(env, team)
        _logger.debug("Existing user profiles for team %s: %s", team, profiles)
        for p in profiles:
            if p["slug"] == profile_name:
                _logger.info("Profile exists, deleting...")
                profiles.remove(p)
                _logger.debug("Updated user profiles for team %s: %s", team, profiles)
                write_context_ssm(profiles, env, team)
                msg_ctx.tip("Profile deleted")
                msg_ctx.progress(100)

                return
        raise Exception(f"Profile {profile_name} not found")


def list_profiles(env: str, team: str, debug: bool) -> None:
    print("Team profiles:")
    profiles: List[Dict[str, Any]] = read_user_profiles_ssm(env, team)
    _logger.debug("Existing user profiles for team %s: %s", team, profiles)
    print(json.dumps(profiles, indent=4, sort_keys=True))

    print("Admin deployed profiles:")
    from aws_orbit_sdk import common_pod_specification

    os.environ["AWS_ORBIT_ENV"] = env
    os.environ["AWS_ORBIT_TEAM_SPACE"] = team
    deployed_profiles: common_pod_specification.PROFILES_TYPE = (
        common_pod_specification.TeamConstants().deployed_profiles()
    )
    print(json.dumps(deployed_profiles, indent=4, sort_keys=True))


def build_profile(env: str, team: str, profile: str, debug: bool) -> None:
    with MessagesContext("Adding profile", debug=debug) as msg_ctx:
        msg_ctx.info("Retrieving existing profiles")
        profiles: List[Dict[str, Any]] = read_user_profiles_ssm(env, team)
        _logger.debug("Existing user profiles for team %s: %s", team, profiles)
        profiles_new = json.loads(profile)
        if isinstance(profiles_new, dict):
            profile_json_list = [cast(Dict[str, Any], profiles_new)]
        else:
            profile_json_list = cast(List[Dict[str, Any]], profiles_new)

        for profile_json in profile_json_list:
            if "slug" not in profile_json:
                # generate missing slug fields from display_name
                profile_json["slug"] = slugify(profile_json["display_name"])
            if "slug" not in profile_json:
                raise Exception("Profile document must include property 'slug'")

            _logger.debug(f"new profile name: {profile_json['display_name']}")
            for p in profiles:
                if p["slug"] == profile_json["slug"]:
                    _logger.info("Profile exists, updating...")
                    profiles.remove(p)
                    break

            profiles.append(profile_json)
            msg_ctx.tip(f"Profile added {profile_json['display_name']}")
            _logger.debug("Updated user profiles for team %s: %s", team, profiles)
        write_context_ssm(profiles, env, team)
        msg_ctx.progress(100)


def build_image(
    env: str,
    dir: Optional[str],
    name: str,
    script: Optional[str],
    build_args: Optional[List[str]],
    timeout: int = 30,
    debug: bool = False,
    source_registry: Optional[str] = None,
    source_repository: Optional[str] = None,
    source_version: Optional[str] = None,
) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as msg_ctx:
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
        msg_ctx.info("Manifest loaded")
        if cfn.does_stack_exist(stack_name=f"orbit-{context.name}") is False:
            msg_ctx.error("Please, deploy your environment before deploying any additional docker image")
            return
        msg_ctx.progress(3)
        if dir:
            dirs = [(dir, name)]
        else:
            dirs = []
        bundle_path = bundle.generate_bundle(command_name=f"deploy_image-{name}", context=context, dirs=dirs)
        msg_ctx.progress(5)

        script_str = "NO_SCRIPT" if script is None else script
        source_str = "NO_REPO" if source_registry is None else f"{source_registry} {source_repository} {source_version}"
        build_args = [] if build_args is None else build_args
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=False,
            cmds_build=[
                f"orbit remote --command build_image " f"{env} {name} {script_str} {source_str} {' '.join(build_args)}"
            ],
            changeset=None,
        )
        msg_ctx.progress(6)

        remote.run(
            command_name=f"deploy_image-{name}",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=timeout,
        )
        msg_ctx.info("Docker Image deploy into ECR")

        address = (
            f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}/{name}"
            if name in [n.replace("_", "-") for n in context.images.names]
            else f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}/users/{name}"
        )

        msg_ctx.info(f"ECR Image Address={address}")
        msg_ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        msg_ctx.progress(100)
