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
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Union, cast

from datamaker_cli import utils

if TYPE_CHECKING:
    from datamaker_cli.manifest import Manifest
    from datamaker_cli.manifest.team import TeamManifest
    from datamaker_cli.messages import MessagesContext

HOOK_TYPE = Optional[Callable[["Manifest", "TeamManifest"], Union[None, List[str]]]]

_logger: logging.Logger = logging.getLogger(__name__)


class PluginRegistry:
    def __init__(
        self,
        name: str,
        team_name: str,
        deploy_demo_hook: Optional[Callable[["Manifest"], None]] = None,
        destroy_demo_hook: Optional[Callable[["Manifest"], None]] = None,
        deploy_env_hook: Optional[Callable[["Manifest"], None]] = None,
        destroy_env_hook: Optional[Callable[["Manifest"], None]] = None,
        deploy_team_hook: Optional[Callable[["Manifest", "TeamManifest"], None]] = None,
        destroy_team_hook: Optional[Callable[["Manifest", "TeamManifest"], None]] = None,
        dockerfile_injection_hook: Optional[Callable[["Manifest", "TeamManifest"], List[str]]] = None,
    ) -> None:
        self.name = name
        self.team_name = team_name
        self._deploy_demo_hook: Optional[Callable[["Manifest"], None]] = deploy_demo_hook
        self._destroy_demo_hook: Optional[Callable[["Manifest"], None]] = destroy_demo_hook
        self._deploy_env_hook: Optional[Callable[["Manifest"], None]] = deploy_env_hook
        self._destroy_env_hook: Optional[Callable[["Manifest"], None]] = destroy_env_hook
        self._deploy_team_hook: Optional[Callable[["Manifest", "TeamManifest"], None]] = deploy_team_hook
        self._destroy_team_hook: Optional[Callable[["Manifest", "TeamManifest"], None]] = destroy_team_hook
        self._dockerfile_injection_hook: Optional[
            Callable[["Manifest", "TeamManifest"], List[str]]
        ] = dockerfile_injection_hook

    """
    DEMO
    """

    @property
    def deploy_demo_hook(self) -> Optional[Callable[["Manifest"], None]]:
        return self._deploy_demo_hook

    @deploy_demo_hook.setter
    def deploy_demo_hook(self, func: Optional[Callable[["Manifest"], None]]) -> None:
        self._deploy_demo_hook = func

    @deploy_demo_hook.deleter
    def deploy_demo_hook(self) -> None:
        self._deploy_demo_hook = None

    @property
    def destroy_demo_hook(self) -> Optional[Callable[["Manifest"], None]]:
        return self._destroy_demo_hook

    @destroy_demo_hook.setter
    def destroy_demo_hook(self, func: Optional[Callable[["Manifest"], None]]) -> None:
        self._destroy_demo_hook = func

    @destroy_demo_hook.deleter
    def destroy_demo_hook(self) -> None:
        self._destroy_demo_hook = None

    """
    ENV
    """

    @property
    def deploy_env_hook(self) -> Optional[Callable[["Manifest"], None]]:
        return self._deploy_env_hook

    @deploy_env_hook.setter
    def deploy_env_hook(self, func: Optional[Callable[["Manifest"], None]]) -> None:
        self._deploy_env_hook = func

    @deploy_env_hook.deleter
    def deploy_env_hook(self) -> None:
        self._deploy_env_hook = None

    @property
    def destroy_env_hook(self) -> Optional[Callable[["Manifest"], None]]:
        return self._destroy_env_hook

    @destroy_env_hook.setter
    def destroy_env_hook(self, func: Optional[Callable[["Manifest"], None]]) -> None:
        self._destroy_env_hook = func

    @destroy_env_hook.deleter
    def destroy_env_hook(self) -> None:
        self._destroy_env_hook = None

    """
    TEAM
    """

    @property
    def deploy_team_hook(self) -> Optional[Callable[["Manifest", "TeamManifest"], None]]:
        return self._deploy_team_hook

    @deploy_team_hook.setter
    def deploy_team_hook(self, func: Optional[Callable[["Manifest", "TeamManifest"], None]]) -> None:
        self._deploy_team_hook = func

    @deploy_team_hook.deleter
    def deploy_team_hook(self) -> None:
        self._deploy_team_hook = None

    @property
    def destroy_team_hook(self) -> Optional[Callable[["Manifest", "TeamManifest"], None]]:
        return self._destroy_team_hook

    @destroy_team_hook.setter
    def destroy_team_hook(self, func: Optional[Callable[["Manifest", "TeamManifest"], None]]) -> None:
        self._destroy_team_hook = func

    @destroy_team_hook.deleter
    def destroy_team_hook(self) -> None:
        self._destroy_team_hook = None

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


class PluginRegistries:
    def __init__(self) -> None:
        self._manifest: Optional["Manifest"] = None
        self._registries: Dict[str, Dict[str, "PluginRegistry"]] = {}

    def load_plugins(self, manifest: "Manifest", ctx: Optional["MessagesContext"] = None) -> None:
        self._manifest = manifest
        for team_manifest in manifest.teams:
            for plugin in team_manifest.plugins:
                _logger.debug(f"{team_manifest.name} Plugin load: {plugin.name}")
                if ctx is not None:
                    ctx.info(f"Loading plugin {plugin.name} for the {team_manifest.name} team")
                if team_manifest.name not in self._registries:
                    self._registries[team_manifest.name] = {}
                self._registries[team_manifest.name][plugin.name] = PluginRegistry(
                    name=plugin.name, team_name=team_manifest.name
                )
                importlib.import_module(plugin.name)

    def _hook_call(self, manifest: "Manifest", hook_name: str) -> None:
        self._manifest = manifest
        for team_manifest in manifest.teams:
            for plugin in team_manifest.plugins:
                hook = self._registries[team_manifest.name][plugin.name].__getattribute__(hook_name)
                if hook is not None:
                    _logger.debug(f"Running {hook_name} for {team_manifest.name} -> {plugin.name}")
                    hook(manifest, team_manifest)

    def deploy_demo(self, manifest: "Manifest") -> None:
        self._hook_call(manifest=manifest, hook_name="deploy_demo_hook")

    def deploy_env(self, manifest: "Manifest") -> None:
        self._hook_call(manifest=manifest, hook_name="deploy_env_hook")

    def deploy_teams(self, manifest: "Manifest") -> None:
        self._hook_call(manifest=manifest, hook_name="deploy_team_hook")

    def destroy_demo(self, manifest: "Manifest") -> None:
        self._hook_call(manifest=manifest, hook_name="destroy_demo_hook")

    def destroy_env(self, manifest: "Manifest") -> None:
        self._hook_call(manifest=manifest, hook_name="destroy_env_hook")

    def destroy_teams(self, manifest: "Manifest") -> None:
        self._hook_call(manifest=manifest, hook_name="destroy_team_hook")

    def add_hook(self, hook_name: str, func: Callable[["Manifest", "TeamManifest"], Union[None, List[str]]]) -> None:
        if self._manifest is None:
            raise RuntimeError("Empty PLUGINS_REGISTRIES. Please, run load_plugins() before try to add hooks.")
        plugin_name: str = utils.extract_plugin_name(func=func)
        for team_manifest in self._manifest.teams:
            if team_manifest.get_plugin_by_name(name=plugin_name) is not None:
                self._registries[team_manifest.name][plugin_name].__setattr__(hook_name, func)

    def get_hook(self, manifest: "Manifest", team_name: str, plugin_name: str, hook_name: str) -> HOOK_TYPE:
        self._manifest = manifest
        return cast(HOOK_TYPE, self._registries[team_name][plugin_name].__getattribute__(hook_name))


PLUGINS_REGISTRIES: PluginRegistries = PluginRegistries()

from datamaker_cli.plugins import hooks  # noqa: F401,E402
