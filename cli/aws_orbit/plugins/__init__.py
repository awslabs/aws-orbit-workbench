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

import importlib
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Union, cast

from aws_orbit import utils
from aws_orbit.services import s3

if TYPE_CHECKING:
    from aws_orbit.messages import MessagesContext
    from aws_orbit.models.changeset import PluginChangeset, TeamsChangeset
    from aws_orbit.models.context import Context, TeamContext

HOOK_FUNC_TYPE = Callable[[str, "Context", "TeamContext", Dict[str, Any]], Union[None, List[str], str]]
HOOK_TYPE = Optional[HOOK_FUNC_TYPE]

_logger: logging.Logger = logging.getLogger(__name__)


class PluginRegistry:
    def __init__(
        self,
        plugin_id: str,
        module: str,
        team_name: str,
        parameters: Dict[str, Any],
        deploy_hook: HOOK_TYPE = None,
        destroy_hook: HOOK_TYPE = None,
        dockerfile_injection_hook: HOOK_TYPE = None,
        bootstrap_injection_hook: HOOK_TYPE = None,
        pre_hook: HOOK_TYPE = None,
        post_hook: HOOK_TYPE = None,
    ) -> None:
        self.plugin_id: str = plugin_id
        self.team_name: str = team_name
        self.module_name: str = module
        self.parameters: Dict[str, Any] = parameters
        self._deploy_hook: HOOK_TYPE = deploy_hook
        self._destroy_hook: HOOK_TYPE = destroy_hook
        self._dockerfile_injection_hook: HOOK_TYPE = dockerfile_injection_hook
        self._bootstrap_injection_hook: HOOK_TYPE = bootstrap_injection_hook
        self._pre_hook: HOOK_TYPE = pre_hook
        self._post_hook: HOOK_TYPE = post_hook

    def destroy(self, context: "Context", team_context: "TeamContext") -> None:
        if self.bootstrap_injection_hook is not None:
            if context.toolkit.s3_bucket is None:
                raise ValueError("manifest.toolkit_s3_bucket is None!")
            key: str = f"{team_context.bootstrap_s3_prefix}{self.plugin_id}.sh"
            s3.delete_objects(bucket=context.toolkit.s3_bucket, keys=[key])
            _logger.debug(f"s3://{context.toolkit.s3_bucket}/{key} deleted")
        else:
            _logger.debug(
                (
                    f"Skipping {self.plugin_id} bootstrap deletion for team {team_context.name} "
                    "because it does not have bootstrap_injection hook registered."
                )
            )
        if self.destroy_hook is None:
            _logger.debug(
                (
                    f"Skipping {self.plugin_id} destroy for team {team_context.name} "
                    "because it does not have destroy hook registered."
                )
            )
            return None
        _logger.debug(f"Destroying plugin {self.plugin_id} for team {team_context.name}")
        self.destroy_hook(self.plugin_id, context, team_context, self.parameters)

    """
    Deploy / Destroy
    """

    @property
    def deploy_hook(self) -> HOOK_TYPE:
        return self._deploy_hook

    @deploy_hook.setter
    def deploy_hook(self, func: HOOK_TYPE) -> None:
        self._deploy_hook = func

    @deploy_hook.deleter
    def deploy_hook(self) -> None:
        self._deploy_hook = None

    @property
    def destroy_hook(self) -> HOOK_TYPE:
        return self._destroy_hook

    @destroy_hook.setter
    def destroy_hook(self, func: HOOK_TYPE) -> None:
        self._destroy_hook = func

    @destroy_hook.deleter
    def destroy_hook(self) -> None:
        self._destroy_hook = None

    """
    IMAGE
    """

    @property
    def dockerfile_injection_hook(self) -> HOOK_TYPE:
        return self._dockerfile_injection_hook

    @dockerfile_injection_hook.setter
    def dockerfile_injection_hook(self, func: HOOK_TYPE) -> None:
        self._dockerfile_injection_hook = func

    @dockerfile_injection_hook.deleter
    def dockerfile_injection_hook(self) -> None:
        self._dockerfile_injection_hook = None

    @property
    def bootstrap_injection_hook(self) -> HOOK_TYPE:
        return self._bootstrap_injection_hook

    @bootstrap_injection_hook.setter
    def bootstrap_injection_hook(self, func: HOOK_TYPE) -> None:
        self._bootstrap_injection_hook = func

    @bootstrap_injection_hook.deleter
    def bootstrap_injection_hook(self) -> None:
        self._bootstrap_injection_hook = None

    """
    PRE AND POST hooks. Used for deploying and destroying CloudFormation based resources as part of team stacks.
    Cloudformation file path should be part of the custom_cfn parameters.
    """

    @property
    def pre_hook(self) -> HOOK_TYPE:
        return self._pre_hook

    @pre_hook.setter
    def pre_hook(self, func: HOOK_TYPE) -> None:
        self._pre_hook = func

    @pre_hook.deleter
    def pre_hook(self) -> None:
        self._pre_hook = None

    @property
    def post_hook(self) -> HOOK_TYPE:
        return self._post_hook

    @post_hook.setter
    def post_hook(self, func: HOOK_TYPE) -> None:
        self._post_hook = func

    @post_hook.deleter
    def post_hook(self) -> None:
        self._post_hook = None


class PluginRegistries:
    def __init__(self) -> None:
        self._context: Optional["Context"] = None
        self._registries: Dict[str, Dict[str, "PluginRegistry"]] = {}
        self._plugin_changesets: List["PluginChangeset"] = []
        self._teams_changeset: Optional["TeamsChangeset"] = None

    def load_plugins(
        self,
        context: "Context",
        plugin_changesets: List["PluginChangeset"],
        teams_changeset: Optional["TeamsChangeset"],
        msg_ctx: Optional["MessagesContext"] = None,
    ) -> None:
        self._context = context
        self._plugin_changesets = plugin_changesets
        self._teams_changeset = teams_changeset
        imports_names: Set[Optional[str]] = set()
        _logger.debug("Loading Plugins...")

        # CURRENT
        for team_context in context.teams:
            if team_context.name not in self._registries:
                self._registries[team_context.name] = {}
            for plugin in team_context.plugins:
                if msg_ctx is not None:
                    msg_ctx.info(f"Loading plugin {plugin.plugin_id} for the {team_context.name} team")
                _logger.debug(
                    f"Loading plugin {plugin.plugin_id} for the {team_context.name} team (changeset) [CURRENT]"
                )
                self._registries[team_context.name][plugin.plugin_id] = PluginRegistry(
                    plugin_id=plugin.plugin_id,
                    team_name=team_context.name,
                    parameters=plugin.parameters,
                    module=plugin.module,
                )
                imports_names.add(plugin.module)

        for change in plugin_changesets:
            if change.team_name not in self._registries:
                self._registries[change.team_name] = {}

            # OLD
            for plugin_id in change.old:
                if msg_ctx is not None:
                    msg_ctx.info(f"Loading plugin {plugin_id} for the {change.team_name} team (changeset)")
                _logger.debug(f"Loading plugin {plugin_id} for the {change.team_name} team (changeset) [OLD]")
                self._registries[change.team_name][plugin_id] = PluginRegistry(
                    plugin_id=plugin_id,
                    team_name=change.team_name,
                    parameters=change.old_parameters[plugin_id],
                    module=change.old_modules[plugin_id],
                )
                imports_names.add(change.old_modules[plugin_id])

            # NEW
            for plugin_id in change.new:
                if msg_ctx is not None:
                    msg_ctx.info(f"Loading plugin {plugin_id} for the {change.team_name} team (changeset)")
                _logger.debug(f"Loading plugin {plugin_id} for the {change.team_name} team (changeset) [NEW]")
                self._registries[change.team_name][plugin_id] = PluginRegistry(
                    plugin_id=plugin_id,
                    team_name=change.team_name,
                    parameters=change.new_parameters[plugin_id],
                    module=change.new_modules[plugin_id],
                )
                imports_names.add(change.new_modules[plugin_id])

        _logger.debug("imports_names: %s", imports_names)
        for name in imports_names:
            if name is not None:
                _logger.debug("Importing %s", name)
                importlib.import_module(name)

        _logger.debug("Plugins Loaded.")

    def add_hook(self, hook_name: str, func: HOOK_FUNC_TYPE) -> None:
        if self._context is None:
            raise RuntimeError("Empty PLUGINS_REGISTRIES. Please, run load_plugins() before try to add hooks.")
        plugin_module_name: str = utils.extract_plugin_module_name(func=func)
        _logger.debug("Adding hook %s for %s", hook_name, plugin_module_name)

        teams_names: List[str] = [t.name for t in self._context.teams]
        if self._teams_changeset is not None:
            for team_name in self._teams_changeset.removed_teams_names + self._teams_changeset.added_teams_names:
                if team_name not in teams_names:
                    teams_names.append(team_name)

        _logger.debug("teams_names: %s", teams_names)
        for team_name in teams_names:
            if team_name in self._registries:
                for plugin_name, registry in self._registries[team_name].items():
                    if registry.module_name == plugin_module_name:
                        self._registries[team_name][plugin_name].__setattr__(hook_name, func)
                        _logger.debug(
                            "Team %s / Plugin %s (%s): %s REGISTERED.",
                            team_name,
                            plugin_name,
                            plugin_module_name,
                            hook_name,
                        )

    def get_hook(self, context: "Context", team_name: str, plugin_name: str, hook_name: str) -> HOOK_TYPE:
        self._context = context
        if plugin_name not in self._registries[team_name]:
            return cast(HOOK_TYPE, None)
        return cast(HOOK_TYPE, self._registries[team_name][plugin_name].__getattribute__(hook_name))

    def destroy_plugin(self, context: "Context", team_context: "TeamContext", plugin_id: str) -> None:
        self._context = context
        if plugin_id not in self._registries[team_context.name]:
            _logger.debug(
                ("Skipping %s deletion for team %s because it is not registered.", plugin_id, team_context.name)
            )
        _logger.debug("Destroying %s for team %s.", plugin_id, team_context.name)
        self._registries[team_context.name][plugin_id].destroy(context=context, team_context=team_context)
        if plugin_id != "custom_cfn":
            del self._registries[team_context.name][plugin_id]

    def destroy_team_plugins(self, context: "Context", team_context: "TeamContext") -> None:
        self._context = context
        if team_context.name in self._registries:
            _logger.debug(f"registries: {self._registries}")
            plugins_ids: List[str] = list(self._registries[team_context.name].keys())
            _logger.debug(f"plugins_ids: {plugins_ids}")
            for plugin_id in plugins_ids:
                self.destroy_plugin(context=context, team_context=team_context, plugin_id=plugin_id)
        else:
            _logger.debug(
                "Skipping destroy_team_plugins for %s because there is no plugins registered.", team_context.name
            )

    def deploy_plugin(self, context: "Context", team_context: "TeamContext", plugin_id: str) -> None:
        self._context = context
        if team_context.name in self._registries:
            if plugin_id not in self._registries[team_context.name]:
                _logger.debug(
                    (f"Skipping {plugin_id} deploy for team {team_context.name} because it is not registered.")
                )
                return None
            hook: HOOK_TYPE = self._registries[team_context.name][plugin_id].deploy_hook
            parameters: Dict[str, Any] = self._registries[team_context.name][plugin_id].parameters
            if hook is None:
                _logger.debug(
                    (
                        f"Skipping {plugin_id} deploy for team {team_context.name} "
                        "because it does not have deploy hook registered."
                    )
                )
                return None
            _logger.debug(f"Deploying {plugin_id} for team {team_context.name}.")
            hook(plugin_id, context, team_context, parameters)
        else:
            _logger.debug(
                "Skipping deploy_plugin for %s/%s because there is no plugins registered.",
                team_context.name,
                plugin_id,
            )

    @staticmethod
    def _is_plugin_removed(changes: List["PluginChangeset"], plugin_id: str, team_name: str) -> bool:
        for change in changes:
            if change.team_name == team_name:
                if plugin_id not in change.new:
                    return True
        return False

    def deploy_team_plugins(
        self, context: "Context", team_context: "TeamContext", changes: List["PluginChangeset"]
    ) -> None:
        self._context = context
        if team_context.name in self._registries:
            plugins_ids: List[str] = list(self._registries[team_context.name].keys())
            for plugin_id in plugins_ids:
                if self._is_plugin_removed(changes=changes, plugin_id=plugin_id, team_name=team_context.name):
                    self.destroy_plugin(context=context, team_context=team_context, plugin_id=plugin_id)

                else:
                    _logger.debug("Deploying plugin %s for team %s", plugin_id, team_context.name)
                    self.deploy_plugin(context=context, team_context=team_context, plugin_id=plugin_id)
        else:
            _logger.debug(
                "Skipping deploy_team_plugins for %s because there is no plugins registered.", team_context.name
            )


PLUGINS_REGISTRIES: PluginRegistries = PluginRegistries()
