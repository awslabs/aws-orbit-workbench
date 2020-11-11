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
import pprint
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set, Union, cast

from datamaker_cli import utils
from datamaker_cli.services import s3

if TYPE_CHECKING:
    from datamaker_cli.changeset import PluginChangeset
    from datamaker_cli.manifest import Manifest
    from datamaker_cli.manifest.team import TeamManifest
    from datamaker_cli.messages import MessagesContext

HOOK_FUNC_TYPE = Callable[["Manifest", "TeamManifest"], Union[None, List[str], str]]
HOOK_TYPE = Optional[HOOK_FUNC_TYPE]

_logger: logging.Logger = logging.getLogger(__name__)


class PluginRegistry:
    def __init__(
        self,
        name: str,
        team_name: str,
        deploy_hook: Optional[Callable[["Manifest", "TeamManifest"], None]] = None,
        destroy_hook: Optional[Callable[["Manifest", "TeamManifest"], None]] = None,
        dockerfile_injection_hook: Optional[Callable[["Manifest", "TeamManifest"], List[str]]] = None,
        bootstrap_injection_hook: Optional[Callable[["Manifest", "TeamManifest"], str]] = None,
    ) -> None:
        self.name = name
        self.team_name = team_name
        self._deploy_hook: Optional[Callable[["Manifest", "TeamManifest"], None]] = deploy_hook
        self._destroy_hook: Optional[Callable[["Manifest", "TeamManifest"], None]] = destroy_hook
        self._dockerfile_injection_hook: Optional[
            Callable[["Manifest", "TeamManifest"], List[str]]
        ] = dockerfile_injection_hook
        self._bootstrap_injection_hook: Optional[Callable[["Manifest", "TeamManifest"], str]] = bootstrap_injection_hook

    def destroy(self, manifest: "Manifest", team_manifest: "TeamManifest") -> None:
        if self.bootstrap_injection_hook is not None:
            if manifest.toolkit_s3_bucket is None:
                raise ValueError(f"manifest.toolkit_s3_bucket: {manifest.toolkit_s3_bucket}")
            key: str = f"{team_manifest.bootstrap_s3_prefix}{self.name}.sh"
            s3.delete_objects(manifest=manifest, bucket=manifest.toolkit_s3_bucket, keys=[key])
            _logger.debug(f"s3://{manifest.toolkit_s3_bucket}/{key} deleted")
        else:
            _logger.debug(
                (
                    f"Skipping {self.name} bootstrap deletion for team {team_manifest.name} "
                    "because it does not have bootstrap_injection hook registered."
                )
            )
        if self.destroy_hook is None:
            _logger.debug(
                (
                    f"Skipping {self.name} destroy for team {team_manifest.name} "
                    "because it does not have destroy hook registered."
                )
            )
            return None
        _logger.debug(f"Destroying plugin {self.name} for team {team_manifest.name}")
        self.destroy_hook(manifest, team_manifest)

    """
    Deploy / Destroy
    """

    @property
    def deploy_hook(self) -> Optional[Callable[["Manifest", "TeamManifest"], None]]:
        return self._deploy_hook

    @deploy_hook.setter
    def deploy_hook(self, func: Optional[Callable[["Manifest", "TeamManifest"], None]]) -> None:
        self._deploy_hook = func

    @deploy_hook.deleter
    def deploy_hook(self) -> None:
        self._deploy_hook = None

    @property
    def destroy_hook(self) -> Optional[Callable[["Manifest", "TeamManifest"], None]]:
        return self._destroy_hook

    @destroy_hook.setter
    def destroy_hook(self, func: Optional[Callable[["Manifest", "TeamManifest"], None]]) -> None:
        self._destroy_hook = func

    @destroy_hook.deleter
    def destroy_hook(self) -> None:
        self._destroy_hook = None

    """
    IMAGE
    """

    @property
    def dockerfile_injection_hook(self) -> Optional[Callable[["Manifest", "TeamManifest"], List[str]]]:
        return self._dockerfile_injection_hook

    @dockerfile_injection_hook.setter
    def dockerfile_injection_hook(self, func: Optional[Callable[["Manifest", "TeamManifest"], List[str]]]) -> None:
        self._dockerfile_injection_hook = func

    @dockerfile_injection_hook.deleter
    def dockerfile_injection_hook(self) -> None:
        self._dockerfile_injection_hook = None

    @property
    def bootstrap_injection_hook(self) -> Optional[Callable[["Manifest", "TeamManifest"], str]]:
        return self._bootstrap_injection_hook

    @bootstrap_injection_hook.setter
    def bootstrap_injection_hook(self, func: Optional[Callable[["Manifest", "TeamManifest"], str]]) -> None:
        self._bootstrap_injection_hook = func

    @bootstrap_injection_hook.deleter
    def bootstrap_injection_hook(self) -> None:
        self._bootstrap_injection_hook = None


class PluginRegistries:
    def __init__(self) -> None:
        self._manifest: Optional["Manifest"] = None
        self._registries: Dict[str, Dict[str, "PluginRegistry"]] = {}

    def load_plugins(
        self, manifest: "Manifest", changes: List["PluginChangeset"], ctx: Optional["MessagesContext"] = None
    ) -> None:
        self._manifest = manifest
        candidates: Dict[str, Set[str]] = {}
        for team_manifest in manifest.teams:
            if team_manifest.name not in candidates:
                candidates[team_manifest.name] = set()
            for plugin in team_manifest.plugins:
                candidates[team_manifest.name].add(plugin.name)
        for change in changes:
            if change.team_name not in candidates:
                candidates[change.team_name] = set()
            for plugin_name in change.old:
                candidates[change.team_name].add(plugin_name)
        _logger.debug("Plugins load candidates:\n%s", pprint.pformat(candidates))

        imports_names: Set[str] = set()
        for team_name, plugins_names in candidates.items():
            for plugin_name in plugins_names:
                _logger.debug("%s Plugin load: %s", team_name, plugin_name)
                if ctx is not None:
                    ctx.info(f"Loading plugin {plugin_name} for the {team_name} team")
                if team_name not in self._registries:
                    self._registries[team_name] = {}
                self._registries[team_name][plugin_name] = PluginRegistry(name=plugin_name, team_name=team_name)
                imports_names.add(plugin_name)

        _logger.debug("imports_names: %s", imports_names)
        for name in imports_names:
            _logger.debug("Importing %s", name)
            importlib.import_module(name)

    def add_hook(self, hook_name: str, func: HOOK_FUNC_TYPE) -> None:
        if self._manifest is None:
            raise RuntimeError("Empty PLUGINS_REGISTRIES. Please, run load_plugins() before try to add hooks.")
        plugin_name: str = utils.extract_plugin_name(func=func)
        for team_manifest in self._manifest.teams:
            if team_manifest.name in self._registries and plugin_name in self._registries[team_manifest.name]:
                self._registries[team_manifest.name][plugin_name].__setattr__(hook_name, func)
                _logger.debug("Team %s / Plugin %s: %s registered.", team_manifest.name, plugin_name, hook_name)
            else:
                _logger.debug(
                    "Team %s / Plugin %s: %s skipping registration.", team_manifest.name, plugin_name, hook_name
                )

    def get_hook(self, manifest: "Manifest", team_name: str, plugin_name: str, hook_name: str) -> HOOK_TYPE:
        self._manifest = manifest
        return cast(HOOK_TYPE, self._registries[team_name][plugin_name].__getattribute__(hook_name))

    def destroy_plugin(self, manifest: "Manifest", team_manifest: "TeamManifest", plugin_name: str) -> None:
        self._manifest = manifest
        if plugin_name not in self._registries[team_manifest.name]:
            _logger.debug(
                ("Skipping %s deletion for team %s because it is not registered.", plugin_name, team_manifest.name)
            )
        _logger.debug("Destroying %s for team %s.", plugin_name, team_manifest.name)
        self._registries[team_manifest.name][plugin_name].destroy(manifest=manifest, team_manifest=team_manifest)
        del self._registries[team_manifest.name][plugin_name]

    def destroy_team_plugins(self, manifest: "Manifest", team_manifest: "TeamManifest") -> None:
        self._manifest = manifest
        if team_manifest.name in self._registries:
            plugins_names: List[str] = list(self._registries[team_manifest.name].keys())
            for plugin_name in plugins_names:
                self.destroy_plugin(manifest=manifest, team_manifest=team_manifest, plugin_name=plugin_name)
        else:
            _logger.debug(
                "Skipping destroy_team_plugins for %s because there is no plugins registered.", team_manifest.name
            )

    def deploy_plugin(self, manifest: "Manifest", team_manifest: "TeamManifest", plugin_name: str) -> None:
        self._manifest = manifest
        if team_manifest.name in self._registries:
            if plugin_name not in self._registries[team_manifest.name]:
                _logger.debug(
                    (f"Skipping {plugin_name} deploy for team {team_manifest.name} because it is not registered.")
                )
                return None
            hook: HOOK_TYPE = self._registries[team_manifest.name][plugin_name].deploy_hook
            if hook is None:
                _logger.debug(
                    (
                        f"Skipping {plugin_name} deploy for team {team_manifest.name} "
                        "because it does not have deploy hook registered."
                    )
                )
                return None
            _logger.debug(f"Deploying {plugin_name} for team {team_manifest.name}.")
            hook(manifest, team_manifest)
        else:
            _logger.debug(
                "Skipping deploy_plugin for %s/%s because there is no plugins registered.",
                team_manifest.name,
                plugin_name,
            )

    @staticmethod
    def _is_plugin_removed(changes: List["PluginChangeset"], plugin_name: str, team_name: str) -> bool:
        for change in changes:
            if change.team_name == team_name:
                if plugin_name not in change.new:
                    return True
        return False

    def deploy_team_plugins(
        self, manifest: "Manifest", team_manifest: "TeamManifest", changes: List["PluginChangeset"]
    ) -> None:
        self._manifest = manifest
        if team_manifest.name in self._registries:
            plugins_names: List[str] = list(self._registries[team_manifest.name].keys())
            for plugin_name in plugins_names:
                if self._is_plugin_removed(changes=changes, plugin_name=plugin_name, team_name=team_manifest.name):
                    self.destroy_plugin(manifest=manifest, team_manifest=team_manifest, plugin_name=plugin_name)
                else:
                    self.deploy_plugin(manifest=manifest, team_manifest=team_manifest, plugin_name=plugin_name)
        else:
            _logger.debug(
                "Skipping deploy_team_plugins for %s because there is no plugins registered.", team_manifest.name
            )


PLUGINS_REGISTRIES: PluginRegistries = PluginRegistries()

from datamaker_cli.plugins import hooks  # noqa: F401,E402
