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
from typing import Any, Dict, List, Optional, cast

from aws_orbit import bundle, plugins, remote, utils
from aws_orbit.changeset import Changeset, extract_changeset
from aws_orbit.manifest import Manifest
from aws_orbit.messages import MessagesContext, stylize
from aws_orbit.services import cfn, codebuild

_logger: logging.Logger = logging.getLogger(__name__)
PROFILES_TYPE = List[Dict[str, Any]]


def read_user_profiles_ssm(env_name: str, team_name: str) -> PROFILES_TYPE:
    ssm_profile_name = f"/orbit/{env_name}/teams/{team_name}/user/profiles"
    _logger.debug("Trying to read profiles from SSM parameter (%s).", ssm_profile_name)
    client = utils.boto3_client(service_name="ssm")
    json_str: str = client.get_parameter(Name=ssm_profile_name)["Parameter"]["Value"]
    return cast(PROFILES_TYPE, json.loads(json_str))


def write_manifest_ssm(profiles: PROFILES_TYPE, env_name: str, team_name: str) -> None:
    ssm_profile_name = f"/orbit/{env_name}/teams/{team_name}/user/profiles"
    client = utils.boto3_client(service_name="ssm")
    _logger.debug("Writing team %s user profiles to SSM parameter.", team_name)
    json_str = str(json.dumps(obj=profiles, sort_keys=True))
    # resolve any parameters inside team manifest per context
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
    with MessagesContext("Profile Deleted", debug=debug) as ctx:
        ctx.info("Retrieving existing profiles")
        profiles: List[Dict[str, Any]] = read_user_profiles_ssm(env, team)
        _logger.debug("Existing user profiles for team %s: %s", team, profiles)
        for p in profiles:
            if p["display_name"] == profile_name:
                _logger.info("Profile exists, deleting...")
                profiles.remove(p)
                _logger.debug("Updated user profiles for team %s: %s", team, profiles)
                write_manifest_ssm(profiles, env, team)
                ctx.tip("Profile deleted")
                ctx.progress(100)
                return
        raise Exception(f"Profile {profile_name} not found")


def list_profiles(env: str, team: str, debug: bool) -> None:
    profiles: List[Dict[str, Any]] = read_user_profiles_ssm(env, team)
    _logger.debug("Existing user profiles for team %s: %s", team, profiles)

    print(json.dumps(profiles, indent=4, sort_keys=True))


def build_profile(env: str, team: str, profile: str, debug: bool) -> None:
    with MessagesContext("Adding profile", debug=debug) as ctx:
        ctx.info("Retrieving existing profiles")
        profiles: List[Dict[str, Any]] = read_user_profiles_ssm(env, team)
        _logger.debug("Existing user profiles for team %s: %s", team, profiles)
        profile_json = cast(Dict[str, Any], json.loads(profile))
        if "display_name" not in profile_json:
            raise Exception("Profile document must include property 'display_name'")

        profile_name = profile_json["display_name"]
        _logger.debug(f"new profile name: {profile_name}")
        _logger.debug(f"profiles: {profile.__class__} , {profiles}")
        for p in profiles:
            if p["display_name"] == profile_name:
                _logger.info("Profile exists, updating...")
                profiles.remove(p)
                break

        profiles.append(profile_json)
        _logger.debug("Updated user profiles for team %s: %s", team, profiles)
        write_manifest_ssm(profiles, env, team)
        ctx.tip("Profile added")
        ctx.progress(100)


def build_image(
    env: str, dir: str, name: str, script: Optional[str], teams: Optional[List[str]], region: Optional[str], debug: bool
) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as ctx:
        manifest = Manifest(filename=None, env=env, region=region)
        manifest.fillup()
        ctx.info("Manifest loaded")

        if cfn.does_stack_exist(manifest=manifest, stack_name=f"orbit-{manifest.name}") is False:
            ctx.error("Please, deploy your environment before deploy any addicional docker image")
            return

        _logger.debug("Inspecting possible manifest changes...")
        changes: Changeset = extract_changeset(manifest=manifest, ctx=ctx)
        _logger.debug(f"Changeset: {changes.asdict()}")
        ctx.progress(2)

        plugins.PLUGINS_REGISTRIES.load_plugins(
            manifest=manifest,
            ctx=ctx,
            plugin_changesets=changes.plugin_changesets,
            teams_changeset=changes.teams_changeset,
        )
        ctx.progress(3)

        bundle_path = bundle.generate_bundle(
            command_name=f"deploy_image-{name}", manifest=manifest, dirs=[(dir, name)], changeset=changes
        )
        ctx.progress(4)
        script_str = "NO_SCRIPT" if script is None else script
        teams_str = "NO_TEAMS" if not teams else ",".join(teams)
        buildspec = codebuild.generate_spec(
            manifest=manifest,
            plugins=True,
            cmds_build=[f"orbit remote --command build_image {env} {name} {script_str} {teams_str}"],
            changeset=changes,
        )
        remote.run(
            command_name=f"deploy_image-{name}",
            manifest=manifest,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=ctx.progress_bar_callback,
            timeout=15,
        )
        ctx.info("Docker Image deploy into ECR")
        address = f"{manifest.account_id}.dkr.ecr.{manifest.region}.amazonaws.com/orbit-{manifest.name}-{name}"
        ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        ctx.progress(100)
