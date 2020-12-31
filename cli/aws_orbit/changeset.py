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
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast

from aws_orbit.manifest import get_team_by_name
from aws_orbit.manifest import team as manifest_team

if TYPE_CHECKING:
    from aws_orbit.manifest import Manifest
    from aws_orbit.manifest.plugin import MANIFEST_FILE_PLUGIN_TYPE
    from aws_orbit.manifest.team import MANIFEST_FILE_TEAM_TYPE, MANIFEST_TEAM_TYPE, TeamManifest
    from aws_orbit.messages import MessagesContext

_logger: logging.Logger = logging.getLogger(__name__)

CHANGESET_FILE_TEAMS_TYPE = Dict[str, Union[List["MANIFEST_FILE_TEAM_TYPE"], List[str]]]
CHANGESET_FILE_PLUGIN_TYPE = Dict[str, Union[str, List[str]]]
CHANGESET_FILE_IMAGE_TYPE = Dict[str, Union[str, None]]
CHANGESET_FILE_EXTERNAL_IDP_TYPE = Dict[str, Union[str, None]]
CHANGESET_FILE_TYPE = Dict[
    str,
    Union[
        List[CHANGESET_FILE_IMAGE_TYPE],
        List[CHANGESET_FILE_PLUGIN_TYPE],
        Optional[CHANGESET_FILE_EXTERNAL_IDP_TYPE],
        Optional[CHANGESET_FILE_TEAMS_TYPE],
    ],
]


class TeamsChangeset:
    def __init__(
        self, old_teams: List["TeamManifest"], new_teams: List["TeamManifest"], removed_teams_names: List[str]
    ) -> None:
        self.old_teams: List["TeamManifest"] = old_teams
        self.new_teams: List["TeamManifest"] = new_teams
        self.removed_teams_names: List[str] = removed_teams_names

    def asdict(self) -> CHANGESET_FILE_TEAMS_TYPE:
        return {
            "old_teams": [t.asdict_file() for t in self.old_teams],
            "new_teams": [t.asdict_file() for t in self.new_teams],
            "removed_teams_names": self.removed_teams_names,
        }


class PluginChangeset:
    def __init__(
        self,
        team_name: str,
        old: List[str],
        new: List[str],
        old_paths: Dict[str, Optional[str]],
        old_parameters: Dict[str, Dict[str, Any]],
        old_modules: Dict[str, str],
    ) -> None:
        self.team_name: str = team_name
        self.old: List[str] = old
        self.new: List[str] = new
        self.old_paths: Dict[str, Optional[str]] = old_paths
        self.old_parameters: Dict[str, Dict[str, Any]] = old_parameters
        self.old_modules: Dict[str, str] = old_modules

    def asdict(self) -> CHANGESET_FILE_IMAGE_TYPE:
        return vars(self)


class ImageChangeset:
    def __init__(self, team_name: str, old_image: Optional[str], new_image: Optional[str]) -> None:
        self.team_name: str = team_name
        self.old_image: Optional[str] = old_image
        self.new_image: Optional[str] = new_image

    def asdict(self) -> CHANGESET_FILE_IMAGE_TYPE:
        return vars(self)


class ExternalIDPChangeset:
    def __init__(
        self,
        old_provider: Optional[str],
        new_provider: Optional[str],
        old_label: Optional[str],
        new_label: Optional[str],
    ) -> None:
        self.old_provider: Optional[str] = old_provider
        self.new_provider: Optional[str] = new_provider
        self.old_label: Optional[str] = old_label
        self.new_label: Optional[str] = new_label

    def asdict(self) -> CHANGESET_FILE_EXTERNAL_IDP_TYPE:
        return vars(self)


class Changeset:
    def __init__(
        self,
        image_changesets: List[ImageChangeset],
        plugin_changesets: List[PluginChangeset],
        external_idp_changeset: Optional[ExternalIDPChangeset],
        teams_changeset: Optional[TeamsChangeset],
    ) -> None:
        self.image_changesets: List[ImageChangeset] = image_changesets
        self.plugin_changesets: List[PluginChangeset] = plugin_changesets
        self.external_idp_changeset: Optional[ExternalIDPChangeset] = external_idp_changeset
        self.teams_changeset: Optional[TeamsChangeset] = teams_changeset

    def asdict(self) -> CHANGESET_FILE_TYPE:
        return {
            "image_changesets": [i.asdict() for i in self.image_changesets],
            "plugin_changesets": [p.asdict() for p in self.plugin_changesets],
            "external_idp_changeset": None
            if self.external_idp_changeset is None
            else self.external_idp_changeset.asdict(),
            "teams_changeset": None if self.teams_changeset is None else self.teams_changeset.asdict(),
        }

    def write_changeset_file(self, filename: str) -> None:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as file:
            json.dump(obj=self.asdict(), fp=file, indent=4, sort_keys=True)
        _logger.debug("Changeset file written: %s", filename)


def _check_images(manifest: "Manifest", ctx: "MessagesContext") -> List[ImageChangeset]:
    image_changesets: List[ImageChangeset] = []
    for team in manifest.teams:
        if team.raw_ssm is None:
            continue
        old_image: Optional[str] = cast(Optional[str], team.raw_ssm.get("image"))
        _logger.debug("Inpecting Image Change for team %s: %s -> %s", team.name, old_image, team.image)
        if team.image != team.raw_ssm.get("image"):
            ctx.info(f"Image change detected for Team {team.name}: {old_image} -> {team.image}")
            image_changesets.append(ImageChangeset(team_name=team.name, old_image=old_image, new_image=team.image))
    return image_changesets


def _check_external_idp(manifest: "Manifest", ctx: "MessagesContext") -> Optional[ExternalIDPChangeset]:
    _logger.debug("Inpecting External IDP Change...")
    if manifest.raw_ssm is None:
        raise RuntimeError("Empty manifest.raw_ssm!")
    old_provider: Optional[str] = cast(Optional[str], manifest.raw_ssm.get("cognito-external-provider", None))
    new_provider: Optional[str] = manifest.cognito_external_provider
    _logger.debug("Provider: %s -> %s", old_provider, new_provider)
    old_label: Optional[str] = cast(Optional[str], manifest.raw_ssm.get("cognito-external-provider-label", None))
    new_label: Optional[str] = manifest.cognito_external_provider_label
    _logger.debug("Label: %s -> %s", old_label, new_label)
    if old_provider != new_provider or old_label != new_label:
        external_idp_changeset: Optional[ExternalIDPChangeset] = ExternalIDPChangeset(
            old_provider=old_provider, new_provider=new_provider, old_label=old_label, new_label=new_label
        )
        ctx.info(f"External IDP change detected: {old_provider} ({old_label}) -> {new_provider} ({new_label})")
    else:
        external_idp_changeset = None
    return external_idp_changeset


def _check_teams(manifest: "Manifest", ctx: "MessagesContext") -> Optional[TeamsChangeset]:
    _logger.debug("Inpecting Teams changes...")
    if manifest.raw_ssm is None:
        raise RuntimeError("Empty manifest.raw_ssm!")
    old_names = sorted(cast(List[str], manifest.raw_ssm.get("teams", [])))
    new_teams: List["TeamManifest"] = deepcopy(manifest.teams)
    new_names: List[str] = sorted([t.name for t in new_teams])
    _logger.debug("Teams: %s -> %s", old_names, new_names)
    removed_teams: Set[str] = set(old_names) - set(new_names)
    _logger.debug("removed_teams: %s", removed_teams)
    if removed_teams:
        raw_old_teams: List["MANIFEST_TEAM_TYPE"] = []
        for name in old_names:
            raw_team = manifest_team.read_raw_manifest_ssm(manifest=manifest, team_name=name)
            if raw_team is None:
                raise RuntimeError(f"Removed team {name} not found into SSM.")
            raw_old_teams.append(raw_team)
        teams_changeset: Optional[TeamsChangeset] = TeamsChangeset(
            old_teams=manifest_team.parse_teams(
                manifest=manifest, raw_teams=cast(List["MANIFEST_FILE_TEAM_TYPE"], raw_old_teams)
            ),
            new_teams=new_teams,
            removed_teams_names=list(removed_teams),
        )
        ctx.info(f"Removed teams: {list(removed_teams)}")
    else:
        teams_changeset = None
    return teams_changeset


def _check_team_plugins(
    team_manifest: "TeamManifest", removed_list: List[str], ctx: "MessagesContext"
) -> Optional[PluginChangeset]:
    if team_manifest.name in removed_list:
        old_names: List[str] = [p.plugin_id for p in team_manifest.plugins]
        if not old_names:
            return None
        return PluginChangeset(
            team_name=team_manifest.name,
            old=old_names,
            new=[],
            old_paths={p.plugin_id: p.path for p in team_manifest.plugins},
            old_parameters={p.plugin_id: p.parameters for p in team_manifest.plugins},
            old_modules={p.plugin_id: p.module for p in team_manifest.plugins},
        )

    if team_manifest.raw_ssm is None:
        _logger.debug("No plugins change detected for %s.", team_manifest.name)
        return None

    new_names = sorted([p.plugin_id for p in team_manifest.plugins])
    old_names = sorted(
        [cast(str, p["id"]) for p in cast(List["MANIFEST_FILE_PLUGIN_TYPE"], team_manifest.raw_ssm.get("plugins", []))]
    )
    _logger.debug("Inpecting Plugins Change for team %s: %s -> %s", team_manifest.name, old_names, new_names)

    if old_names != new_names:
        ctx.info(f"Plugin change detected for Team {team_manifest.name}: {old_names} -> {new_names}")
        old_paths: Dict[str, Optional[str]] = {
            cast(str, p["id"]): cast(str, p["path"])
            for p in cast(List["MANIFEST_FILE_PLUGIN_TYPE"], team_manifest.raw_ssm.get("plugins", []))
        }
        old_parameters: Dict[str, Dict[str, Any]] = {
            cast(str, p["id"]): cast(Dict[str, Any], p.get("parameters", {}))
            for p in cast(List["MANIFEST_FILE_PLUGIN_TYPE"], team_manifest.raw_ssm.get("plugins", []))
        }
        old_modules: Dict[str, str] = {
            cast(str, p["id"]): cast(str, p.get("module", None))
            for p in cast(List["MANIFEST_FILE_PLUGIN_TYPE"], team_manifest.raw_ssm.get("plugins", []))
        }
        return PluginChangeset(
            team_name=team_manifest.name,
            old=old_names,
            new=new_names,
            old_paths=old_paths,
            old_parameters=old_parameters,
            old_modules=old_modules,
        )
    return None


def _check_plugins(
    manifest: "Manifest", ctx: "MessagesContext", teams_changeset: Optional[TeamsChangeset]
) -> List[PluginChangeset]:
    plugin_changesets: List[PluginChangeset] = []

    teams_manifests: List["TeamManifest"] = deepcopy(manifest.teams)  # Existing teams into the manifest
    removed_list: List[str] = teams_changeset.removed_teams_names if teams_changeset else []
    _logger.debug("removed_list: %s", removed_list)
    if teams_changeset and removed_list:  # Removed teams
        teams_manifests += [get_team_by_name(teams=teams_changeset.old_teams, name=x) for x in removed_list]

    for team_manifest in teams_manifests:
        plugin_changeset: Optional[PluginChangeset] = _check_team_plugins(
            team_manifest=team_manifest, removed_list=removed_list, ctx=ctx
        )
        if plugin_changeset is not None:
            plugin_changesets.append(plugin_changeset)

    return plugin_changesets


def extract_changeset(manifest: "Manifest", ctx: "MessagesContext") -> Changeset:
    if manifest.raw_ssm is None:
        return Changeset(image_changesets=[], plugin_changesets=[], external_idp_changeset=None, teams_changeset=None)
    image_changesets: List[ImageChangeset] = _check_images(manifest=manifest, ctx=ctx)
    external_idp_changeset: Optional[ExternalIDPChangeset] = _check_external_idp(manifest=manifest, ctx=ctx)
    teams_changeset: Optional[TeamsChangeset] = _check_teams(manifest=manifest, ctx=ctx)
    plugin_changesets: List[PluginChangeset] = _check_plugins(
        manifest=manifest, ctx=ctx, teams_changeset=teams_changeset
    )
    return Changeset(
        image_changesets=image_changesets,
        plugin_changesets=plugin_changesets,
        external_idp_changeset=external_idp_changeset,
        teams_changeset=teams_changeset,
    )


def _read_changeset_file(filename: str) -> CHANGESET_FILE_TYPE:
    _logger.debug("reading changeset file (%s)", filename)
    with open(filename, "r") as file:
        return cast(CHANGESET_FILE_TYPE, json.load(fp=file))


def read_changeset_file(manifest: "Manifest", filename: str) -> Changeset:
    raw: CHANGESET_FILE_TYPE = _read_changeset_file(filename=filename)

    # External IDP
    raw_external_idp_changeset: Optional[CHANGESET_FILE_EXTERNAL_IDP_TYPE] = cast(
        Optional[CHANGESET_FILE_EXTERNAL_IDP_TYPE], raw.get("external_idp_changeset", None)
    )
    if raw_external_idp_changeset is None:
        external_idp_changeset: Optional[ExternalIDPChangeset] = None
    else:
        external_idp_changeset = ExternalIDPChangeset(
            old_provider=raw_external_idp_changeset["old_provider"],
            new_provider=raw_external_idp_changeset["new_provider"],
            old_label=raw_external_idp_changeset["old_label"],
            new_label=raw_external_idp_changeset["new_label"],
        )

    # Teams
    raw_teams_changesets: CHANGESET_FILE_TEAMS_TYPE = cast(CHANGESET_FILE_TEAMS_TYPE, raw.get("teams_changeset", {}))
    if raw_teams_changesets:
        teams_changeset: Optional[TeamsChangeset] = TeamsChangeset(
            old_teams=manifest_team.parse_teams(
                manifest=manifest,
                raw_teams=cast(List["MANIFEST_FILE_TEAM_TYPE"], raw_teams_changesets.get("old_teams", [])),
            ),
            new_teams=manifest_team.parse_teams(
                manifest=manifest,
                raw_teams=cast(List["MANIFEST_FILE_TEAM_TYPE"], raw_teams_changesets.get("new_teams", [])),
            ),
            removed_teams_names=cast(List[str], raw_teams_changesets.get("removed_teams_names", [])),
        )
    else:
        teams_changeset = None

    return Changeset(
        image_changesets=[
            ImageChangeset(team_name=cast(str, i["team_name"]), old_image=i["old_image"], new_image=i["new_image"])
            for i in cast(List[CHANGESET_FILE_IMAGE_TYPE], raw.get("image_changesets", []))
        ],
        plugin_changesets=[
            PluginChangeset(
                team_name=cast(str, i["team_name"]),
                old=cast(List[str], i["old"]),
                new=cast(List[str], i["new"]),
                old_paths=cast(Dict[str, Optional[str]], i["old_paths"]),
                old_parameters=cast(Dict[str, Dict[str, Any]], i["old_parameters"]),
                old_modules=cast(Dict[str, str], i["old_modules"]),
            )
            for i in cast(List[CHANGESET_FILE_PLUGIN_TYPE], raw.get("plugin_changesets", []))
        ],
        external_idp_changeset=external_idp_changeset,
        teams_changeset=teams_changeset,
    )
