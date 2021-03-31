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

# flake8: noqa: F811

import logging
import os
from copy import deepcopy
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Set, Type, cast

import yaml
from dataclasses import field
from marshmallow import Schema
from marshmallow_dataclass import dataclass

from aws_orbit.models.common import BaseSchema
from aws_orbit.models.manifest import ManagedNodeGroupManifest
from aws_orbit.services import ssm

if TYPE_CHECKING:
    from aws_orbit.messages import MessagesContext
    from aws_orbit.models.context import Context, TeamContext
    from aws_orbit.models.manifest import Manifest, TeamManifest

_logger: logging.Logger = logging.getLogger(__name__)


@dataclass(base_schema=BaseSchema)
class TeamsChangeset:
    Schema: ClassVar[Type[Schema]] = Schema
    removed_teams_names: List[str]
    added_teams_names: List[str]


@dataclass(base_schema=BaseSchema)
class PluginChangeset:
    Schema: ClassVar[Type[Schema]] = Schema
    team_name: str
    old: List[str] = field(default_factory=list)
    old_paths: Dict[str, Optional[str]] = field(default_factory=dict)
    old_parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    old_modules: Dict[str, str] = field(default_factory=dict)
    new: List[str] = field(default_factory=list)
    new_paths: Dict[str, Optional[str]] = field(default_factory=dict)
    new_parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    new_modules: Dict[str, str] = field(default_factory=dict)


@dataclass(base_schema=BaseSchema)
class ImageChangeset:
    Schema: ClassVar[Type[Schema]] = Schema
    team_name: str
    old_image: Optional[str]
    new_image: Optional[str]


@dataclass(base_schema=BaseSchema)
class ExternalIDPChangeset:
    Schema: ClassVar[Type[Schema]] = Schema
    old_provider: Optional[str]
    new_provider: Optional[str]
    old_label: Optional[str]
    new_label: Optional[str]


@dataclass(base_schema=BaseSchema)
class ListChangeset:
    Schema: ClassVar[Type[Schema]] = Schema
    removed_values: Optional[List[Any]] = None
    added_values: Optional[List[Any]] = None


@dataclass(base_schema=BaseSchema)
class ManagedNodeGroupsChangeset:
    Schema: ClassVar[Type[Schema]] = Schema
    removed_nodegroups: List[ManagedNodeGroupManifest]
    added_nodegroups: List[ManagedNodeGroupManifest]
    modified_nodegroups: List[ManagedNodeGroupManifest]


@dataclass(base_schema=BaseSchema)
class Changeset:
    Schema: ClassVar[Type[Schema]] = Schema
    image_changesets: List[ImageChangeset]
    plugin_changesets: List[PluginChangeset]
    external_idp_changeset: Optional[ExternalIDPChangeset]
    teams_changeset: Optional[TeamsChangeset]
    eks_system_masters_roles_changeset: Optional[ListChangeset]
    managed_nodegroups_changeset: Optional[ManagedNodeGroupsChangeset]


def _check_images(manifest: "Manifest", context: "Context", msg_ctx: "MessagesContext") -> List[ImageChangeset]:
    image_changesets: List[ImageChangeset] = []
    for team in context.teams:
        new_team: Optional["TeamManifest"] = manifest.get_team_by_name(team.name)
        if new_team is None:
            continue
        _logger.debug("Inpecting Image Change for team %s: %s -> %s", team.name, team.image, new_team.image)
        if team.image != new_team.image:
            msg_ctx.info(f"Image change detected for Team {team.name}: {team.image} -> {new_team.image}")
            image_changesets.append(ImageChangeset(team_name=team.name, old_image=team.image, new_image=new_team.image))
    return image_changesets


def _check_external_idp(
    manifest: "Manifest", context: "Context", msg_ctx: "MessagesContext"
) -> Optional[ExternalIDPChangeset]:
    _logger.debug("Inpecting External IDP Change...")
    old_provider: Optional[str] = context.cognito_external_provider
    new_provider: Optional[str] = manifest.cognito_external_provider
    _logger.debug("Provider: %s -> %s", old_provider, new_provider)
    old_label: Optional[str] = context.cognito_external_provider_label
    new_label: Optional[str] = manifest.cognito_external_provider_label
    _logger.debug("Label: %s -> %s", old_label, new_label)
    if old_provider != new_provider or old_label != new_label:
        external_idp_changeset: Optional[ExternalIDPChangeset] = ExternalIDPChangeset(
            old_provider=old_provider, new_provider=new_provider, old_label=old_label, new_label=new_label
        )
        msg_ctx.info(f"External IDP change detected: {old_provider} ({old_label}) -> {new_provider} ({new_label})")
    else:
        external_idp_changeset = None
    return external_idp_changeset


def _check_teams(manifest: "Manifest", context: "Context", msg_ctx: "MessagesContext") -> Optional[TeamsChangeset]:
    _logger.debug("Inpecting Teams changes...")
    old_teams: List["TeamContext"] = deepcopy(context.teams)
    old_names = sorted([t.name for t in old_teams])
    new_teams: List["TeamManifest"] = deepcopy(manifest.teams)
    new_names: List[str] = sorted([t.name for t in new_teams])
    _logger.debug("Teams: %s -> %s", old_names, new_names)
    removed_teams: Set[str] = set(old_names) - set(new_names)
    _logger.debug("removed_teams: %s", removed_teams)
    added_teams: Set[str] = set(new_names) - set(old_names)
    _logger.debug("added_teams: %s", added_teams)
    if removed_teams or added_teams:
        teams_changeset: Optional[TeamsChangeset] = TeamsChangeset(
            removed_teams_names=list(removed_teams),
            added_teams_names=list(added_teams),
        )
        msg_ctx.info(f"Removed teams: {list(removed_teams)}")
        msg_ctx.info(f"Added teams: {list(added_teams)}")
    else:
        teams_changeset = None
    return teams_changeset


def _check_team_plugins(
    team_manifest: "TeamManifest", context: "Context", msg_ctx: "MessagesContext"
) -> Optional[PluginChangeset]:
    new_names: List[str] = sorted([p.plugin_id for p in team_manifest.plugins])
    old_team: Optional["TeamContext"] = context.get_team_by_name(name=team_manifest.name)
    if old_team:
        old_names: List[str] = sorted([p.plugin_id for p in old_team.plugins])
    else:
        old_names = []
    _logger.debug("Inpecting Plugins Change for team %s: %s -> %s", team_manifest.name, old_names, new_names)

    if old_names != new_names:
        msg_ctx.info(f"Plugin change detected for Team {team_manifest.name}: {old_names} -> {new_names}")
        return PluginChangeset(
            team_name=team_manifest.name,
            old=old_names,
            old_paths={p.plugin_id: p.path for p in old_team.plugins} if old_team else {},
            old_parameters={p.plugin_id: p.parameters for p in old_team.plugins} if old_team else {},
            old_modules={p.plugin_id: p.module for p in old_team.plugins} if old_team else {},
            new=new_names,
            new_paths={p.plugin_id: p.path for p in team_manifest.plugins},
            new_parameters={p.plugin_id: p.parameters for p in team_manifest.plugins},
            new_modules={p.plugin_id: p.module for p in team_manifest.plugins},
        )
    return None


def _get_team_by_name(teams: List["TeamContext"], name: str) -> Optional["TeamContext"]:
    for t in teams:
        if t.name == name:
            return t
    return None


def _check_plugins(
    manifest: "Manifest", context: "Context", msg_ctx: "MessagesContext", teams_changeset: Optional[TeamsChangeset]
) -> List[PluginChangeset]:
    plugin_changesets: List[PluginChangeset] = []

    removed_list: List[str] = teams_changeset.removed_teams_names if teams_changeset else []
    _logger.debug("removed_list: %s", removed_list)
    if teams_changeset and removed_list:  # Removed teams
        removed_teams: List[Optional["TeamContext"]] = [context.get_team_by_name(name=x) for x in removed_list]
        for team in [x for x in removed_teams if x is not None]:
            old_names: List[str] = [p.plugin_id for p in team.plugins]
            if not old_names:
                continue
            plugin_changesets.append(
                PluginChangeset(
                    team_name=team.name,
                    old=old_names,
                    old_paths={p.plugin_id: p.path for p in team.plugins},
                    old_parameters={p.plugin_id: p.parameters for p in team.plugins},
                    old_modules={p.plugin_id: p.module for p in team.plugins},
                )
            )

    for team_manifest in deepcopy(manifest.teams):  # Existing teams into the manifest
        plugin_changeset: Optional[PluginChangeset] = _check_team_plugins(
            team_manifest=team_manifest, context=context, msg_ctx=msg_ctx
        )
        if plugin_changeset is not None:
            plugin_changesets.append(plugin_changeset)

    return plugin_changesets


def _check_eks_system_masters_roles(
    manifest: "Manifest", context: "Context", msg_ctx: "MessagesContext"
) -> Optional[ListChangeset]:
    _logger.debug("Inpecting EKS system:masters Roles changes...")
    old_roles: List[str] = sorted(cast(List[str], context.eks_system_masters_roles))
    new_roles: List[str] = sorted(cast(List[str], manifest.eks_system_masters_roles))
    _logger.debug("Roles: %s -> %s", old_roles, new_roles)
    removed_roles: List[str] = list(set(old_roles) - set(new_roles))
    added_roles: List[str] = list(set(new_roles) - set(old_roles))
    _logger.debug("removed_roles: %s", removed_roles)
    _logger.debug("added_roles: %s", added_roles)
    if removed_roles or added_roles:
        list_changeset: Optional[ListChangeset] = ListChangeset(removed_values=removed_roles, added_values=added_roles)
        msg_ctx.info(f"Removed system:masters Roles: {list(removed_roles)}")
        msg_ctx.info(f"Added system:masters Roles: {list(added_roles)}")
    else:
        list_changeset = None
    return list_changeset


def _check_managed_nodegroups(
    manifest: "Manifest", context: "Context", msg_ctx: "MessagesContext"
) -> Optional[ManagedNodeGroupsChangeset]:
    _logger.debug("Inpecting Managed NodeGroups changes...")
    old_nodegroups: List[str] = sorted([ng.name for ng in context.managed_nodegroups])
    new_nodegroups: List[str] = sorted([ng.name for ng in manifest.managed_nodegroups])
    _logger.debug("ManagedNodeGroups: %s -> %s", old_nodegroups, new_nodegroups)
    removed_nodegroups: List[str] = list(set(old_nodegroups) - set(new_nodegroups))
    added_nodegroups: List[str] = list(set(new_nodegroups) - set(old_nodegroups))

    modified_nodegroups: List[ManagedNodeGroupManifest] = []
    for ng in manifest.managed_nodegroups:
        current_ng = next((ng for ng in context.managed_nodegroups if ng.name == ng.name), None)
        if current_ng:
            if (
                ng.nodes_num_desired != current_ng.nodes_num_desired
                or ng.nodes_num_max != current_ng.nodes_num_max
                or ng.nodes_num_min != current_ng.nodes_num_min
            ):
                modified_nodegroups.append(ng)

    _logger.debug("removed_nodegroups: %s", removed_nodegroups)
    _logger.debug("added_nodegroups: %s", added_nodegroups)
    _logger.debug("modified_nodegroups: %s", [ng.name for ng in modified_nodegroups])

    if removed_nodegroups or added_nodegroups or modified_nodegroups:
        managed_nodegroups_changeset: Optional[ManagedNodeGroupsChangeset] = ManagedNodeGroupsChangeset(
            removed_nodegroups=[ng for ng in context.managed_nodegroups if ng.name in removed_nodegroups],
            added_nodegroups=[ng for ng in manifest.managed_nodegroups if ng.name in added_nodegroups],
            modified_nodegroups=modified_nodegroups,
        )
        msg_ctx.info(f"Removed ManagedNodeGroups: {list(removed_nodegroups)}")
        msg_ctx.info(f"Added ManagedNodeGroups: {list(added_nodegroups)}")
        msg_ctx.info(f"Modified ManagedNodeGroups: {[ng.name for ng in modified_nodegroups]}")
    else:
        managed_nodegroups_changeset = None
    return managed_nodegroups_changeset


def extract_changeset(manifest: "Manifest", context: "Context", msg_ctx: "MessagesContext") -> Changeset:
    image_changesets: List[ImageChangeset] = _check_images(manifest=manifest, context=context, msg_ctx=msg_ctx)
    external_idp_changeset: Optional[ExternalIDPChangeset] = _check_external_idp(
        manifest=manifest, context=context, msg_ctx=msg_ctx
    )
    teams_changeset: Optional[TeamsChangeset] = _check_teams(manifest=manifest, context=context, msg_ctx=msg_ctx)
    plugin_changesets: List[PluginChangeset] = _check_plugins(
        manifest=manifest, context=context, msg_ctx=msg_ctx, teams_changeset=teams_changeset
    )
    eks_system_masters_roles_changeset: Optional[ListChangeset] = _check_eks_system_masters_roles(
        manifest=manifest, context=context, msg_ctx=msg_ctx
    )
    managed_nodegroups_changeset: Optional[ManagedNodeGroupsChangeset] = _check_managed_nodegroups(
        manifest=manifest, context=context, msg_ctx=msg_ctx
    )
    changeset: Changeset = Changeset(
        image_changesets=image_changesets,
        plugin_changesets=plugin_changesets,
        external_idp_changeset=external_idp_changeset,
        teams_changeset=teams_changeset,
        eks_system_masters_roles_changeset=eks_system_masters_roles_changeset,
        managed_nodegroups_changeset=managed_nodegroups_changeset,
    )
    dump_changeset_to_ssm(env_name=context.name, changeset=changeset)
    return changeset


def dump_changeset_to_ssm(env_name: str, changeset: Changeset) -> None:
    _logger.debug("Writing changeset to SSM parameter.")
    manifest_parameter_name: str = f"/orbit/{env_name}/changeset"
    ssm.put_parameter(name=manifest_parameter_name, obj=Changeset.Schema().dump(changeset))


def dump_changeset_to_str(changeset: Changeset) -> str:
    content: Dict[str, Any] = cast(Dict[str, Any], Changeset.Schema().dump(changeset))
    return cast(str, yaml.dump(content, sort_keys=False))


def load_changeset_from_ssm(env_name: str) -> Optional[Changeset]:
    content = ssm.get_parameter_if_exists(name=f"/orbit/{env_name}/changeset")
    if content is None:
        return None
    return cast(Changeset, Changeset.Schema().load(data=content, many=False, partial=False, unknown="RAISE"))
