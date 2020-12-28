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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast

from datamaker_cli.manifest import team as manifest_team

if TYPE_CHECKING:
    from datamaker_cli.manifest import Manifest
    from datamaker_cli.manifest.plugin import MANIFEST_FILE_PLUGIN_TYPE
    from datamaker_cli.manifest.team import MANIFEST_FILE_TEAM_TYPE, MANIFEST_TEAM_TYPE, TeamManifest
    from datamaker_cli.messages import MessagesContext

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
        old_paths: Dict[str, str],
        old_parameters: Dict[str, Dict[str, Any]],
        old_modules: Dict[str, str],
    ) -> None:
        self.team_name: str = team_name
        self.old: List[str] = old
        self.new: List[str] = new
        self.old_paths: Dict[str, str] = old_paths
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


def extract_changeset(manifest: "Manifest", ctx: "MessagesContext") -> Changeset:
    if manifest.raw_ssm is None:
        return Changeset(image_changesets=[], plugin_changesets=[], external_idp_changeset=None, teams_changeset=None)

    # Images check
    image_changesets: List[ImageChangeset] = []
    for team in manifest.teams:
        if team.raw_ssm is None:
            continue
        old_image: Optional[str] = cast(Optional[str], team.raw_ssm.get("image"))
        _logger.debug("Inpecting Image Change for team %s: %s -> %s", team.name, old_image, team.image)
        if team.image != team.raw_ssm.get("image"):
            ctx.info(f"Image change detected for Team {team.name}: {old_image} -> {team.image}")
            image_changesets.append(ImageChangeset(team_name=team.name, old_image=old_image, new_image=team.image))

    # Plugin check
    plugin_changesets: List[PluginChangeset] = []
    for team in manifest.teams:
        if team.raw_ssm is None:
            continue
        old: List[str] = [
            cast(str, p["id"]) for p in cast(List["MANIFEST_FILE_PLUGIN_TYPE"], team.raw_ssm.get("plugins", []))
        ]
        new: List[str] = [p.plugin_id for p in team.plugins]
        old.sort()
        new.sort()
        _logger.debug("Inpecting Plugins Change for team %s: %s -> %s", team.name, old, new)
        if old != new:
            ctx.info(f"Plugin change detected for Team {team.name}: {old} -> {new}")
            old_paths: Dict[str, str] = {
                cast(str, p["id"]): cast(str, p["path"])
                for p in cast(List["MANIFEST_FILE_PLUGIN_TYPE"], team.raw_ssm.get("plugins", []))
            }
            old_parameters: Dict[str, Dict[str, Any]] = {
                cast(str, p["id"]): cast(Dict[str, Any], p.get("parameters", {}))
                for p in cast(List["MANIFEST_FILE_PLUGIN_TYPE"], team.raw_ssm.get("plugins", []))
            }
            old_modules: Dict[str, str] = {
                cast(str, p["id"]): cast(str, p.get("module", None))
                for p in cast(List["MANIFEST_FILE_PLUGIN_TYPE"], team.raw_ssm.get("plugins", []))
            }
            plugin_changesets.append(
                PluginChangeset(
                    team_name=team.name,
                    old=old,
                    new=new,
                    old_paths=old_paths,
                    old_parameters=old_parameters,
                    old_modules=old_modules,
                )
            )

    # External IDP
    _logger.debug("Inpecting External IDP Change...")
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

    # Teams check
    _logger.debug("Inpecting Teams changes...")
    old_names = sorted(cast(List[str], manifest.raw_ssm.get("teams", [])))
    new_teams: List["TeamManifest"] = manifest.teams
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
                old_paths=cast(Dict[str, str], i["old_paths"]),
                old_parameters=cast(Dict[str, Dict[str, Any]], i["old_parameters"]),
                old_modules=cast(Dict[str, str], i["old_modules"]),
            )
            for i in cast(List[CHANGESET_FILE_PLUGIN_TYPE], raw.get("plugin_changesets", []))
        ],
        external_idp_changeset=external_idp_changeset,
        teams_changeset=teams_changeset,
    )
