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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

import botocore
from kubernetes import config

from aws_orbit import bundle, plugins, remote, sh, utils
from aws_orbit.messages import MessagesContext, stylize
from aws_orbit.models.context import load_context_from_ssm
from aws_orbit.remote_files.utils import get_k8s_context
from aws_orbit.services import cfn, codebuild, ssm

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

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


def restart_jupyterhub(env: str, team: str, msg_ctx: MessagesContext) -> None:
    ssm.cleanup_manifest(env_name=env)
    context: "Context" = load_context_from_ssm(env_name=env)
    msg_ctx.tip("JupyterHub update...")
    msg_ctx.tip("JupyterHub and notebooks in your namespace will be restarted. Please close notebook and login again")
    try:
        k8s_context = get_k8s_context(context=context)
        sh.run(f"kubectl rollout restart deployment jupyterhub  --namespace {team} --context {k8s_context}")
    except config.config_exception.ConfigException:
        # no context , use kubectl without context
        sh.run(f"kubectl rollout restart deployment jupyterhub  --namespace {team}")
    msg_ctx.tip("JupyterHub restarted")


def delete_profile(env: str, team: str, profile_name: str, debug: bool) -> None:
    with MessagesContext("Profile Deleted", debug=debug) as msg_ctx:
        ssm.cleanup_changeset(env_name=env)
        ssm.cleanup_manifest(env_name=env)
        msg_ctx.info("Retrieving existing profiles")
        profiles: List[Dict[str, Any]] = read_user_profiles_ssm(env, team)
        _logger.debug("Existing user profiles for team %s: %s", team, profiles)
        for p in profiles:
            if p["display_name"] == profile_name:
                _logger.info("Profile exists, deleting...")
                profiles.remove(p)
                _logger.debug("Updated user profiles for team %s: %s", team, profiles)
                write_context_ssm(profiles, env, team)
                msg_ctx.tip("Profile deleted")
                msg_ctx.progress(90)
                restart_jupyterhub(env, team, msg_ctx)
                msg_ctx.progress(100)

                return
        raise Exception(f"Profile {profile_name} not found")


def list_profiles(env: str, team: str, debug: bool) -> None:
    ssm.cleanup_changeset(env_name=env)
    ssm.cleanup_manifest(env_name=env)
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
        ssm.cleanup_changeset(env_name=env)
        ssm.cleanup_manifest(env_name=env)
        msg_ctx.info("Retrieving existing profiles")
        profiles: List[Dict[str, Any]] = read_user_profiles_ssm(env, team)
        _logger.debug("Existing user profiles for team %s: %s", team, profiles)
        profiles_new = json.loads(profile)
        if isinstance(profiles_new, dict):
            profile_json_list = [cast(Dict[str, Any], profiles_new)]
        else:
            profile_json_list = cast(List[Dict[str, Any]], profiles_new)

        for profile_json in profile_json_list:
            profile_name = profile_json["display_name"]
            if "display_name" not in profile_json:
                raise Exception("Profile document must include property 'display_name'")

            _logger.debug(f"new profile name: {profile_name}")
            _logger.debug(f"profiles: {profile.__class__} , {profiles}")
            for p in profiles:
                if p["display_name"] == profile_name:
                    _logger.info("Profile exists, updating...")
                    profiles.remove(p)
                    break

            profiles.append(profile_json)
            msg_ctx.tip(f"Profile added {profile_name}")
            _logger.debug("Updated user profiles for team %s: %s", team, profiles)
        write_context_ssm(profiles, env, team)
        msg_ctx.progress(100)


def build_image(
    env: str,
    dir: str,
    name: str,
    script: Optional[str],
    teams: Optional[List[str]],
    build_args: Optional[List[str]],
    debug: bool,
) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as msg_ctx:
        ssm.cleanup_changeset(env_name=env)
        ssm.cleanup_manifest(env_name=env)
        context: "Context" = load_context_from_ssm(env_name=env)
        msg_ctx.info("Manifest loaded")
        if cfn.does_stack_exist(stack_name=f"orbit-{context.name}") is False:
            msg_ctx.error("Please, deploy your environment before deploying any additional docker image")
            return
        msg_ctx.progress(3)

        plugins.PLUGINS_REGISTRIES.load_plugins(
            context=context,
            msg_ctx=msg_ctx,
            plugin_changesets=[],
            teams_changeset=None,
        )
        msg_ctx.progress(4)

        bundle_path = bundle.generate_bundle(
            command_name=f"deploy_image-{name}", context=context, dirs=[(dir, name)], changeset=None, plugins=True
        )
        msg_ctx.progress(5)

        script_str = "NO_SCRIPT" if script is None else script
        teams_str = "NO_TEAMS" if not teams else ",".join(teams)
        build_args = [] if build_args is None else build_args
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=True,
            cmds_build=[
                f"orbit remote --command build_image {env} {name} {script_str} {teams_str} {' '.join(build_args)}"
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
            timeout=30,
        )
        msg_ctx.info("Docker Image deploy into ECR")
        msg_ctx.progress(98)
        address = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}-{name}"
        msg_ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        msg_ctx.progress(100)
