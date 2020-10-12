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
from typing import Callable, Dict, Optional

from datamaker_cli.manifest import Manifest, TeamManifest

PLUGINS_REGISTRY: Dict[str, "PluginRegistry"] = {}

from datamaker_cli.plugins import hooks  # noqa: F401,E402

_logger: logging.Logger = logging.getLogger(__name__)


class PluginRegistry:
    def __init__(
        self,
        name: str,
        deploy_demo_hook: Optional[Callable[[Manifest], None]] = None,
        destroy_demo_hook: Optional[Callable[[Manifest], None]] = None,
        deploy_env_hook: Optional[Callable[[Manifest], None]] = None,
        destroy_env_hook: Optional[Callable[[Manifest], None]] = None,
        deploy_team_hook: Optional[Callable[[Manifest, TeamManifest], None]] = None,
        destroy_team_hook: Optional[Callable[[Manifest, TeamManifest], None]] = None,
    ):
        self.name = name
        self._deploy_demo_hook: Optional[Callable[[Manifest], None]] = deploy_demo_hook
        self._destroy_demo_hook: Optional[Callable[[Manifest], None]] = destroy_demo_hook
        self._deploy_env_hook: Optional[Callable[[Manifest], None]] = deploy_env_hook
        self._destroy_env_hook: Optional[Callable[[Manifest], None]] = destroy_env_hook
        self._deploy_team_hook: Optional[Callable[[Manifest, TeamManifest], None]] = deploy_team_hook
        self._destroy_team_hook: Optional[Callable[[Manifest, TeamManifest], None]] = destroy_team_hook

        # Loading
        PLUGINS_REGISTRY[self.name] = self

    """
    DEMO
    """

    @property
    def deploy_demo_hook(self) -> Optional[Callable[[Manifest], None]]:
        return self._deploy_demo_hook

    @deploy_demo_hook.setter
    def deploy_demo_hook(self, func: Optional[Callable[[Manifest], None]]) -> None:
        self._deploy_demo_hook = func

    @deploy_demo_hook.deleter
    def deploy_demo_hook(self) -> None:
        self._deploy_demo_hook = None

    @property
    def destroy_demo_hook(self) -> Optional[Callable[[Manifest], None]]:
        return self._destroy_demo_hook

    @destroy_demo_hook.setter
    def destroy_demo_hook(self, func: Optional[Callable[[Manifest], None]]) -> None:
        self._destroy_demo_hook = func

    @destroy_demo_hook.deleter
    def destroy_demo_hook(self) -> None:
        self._destroy_demo_hook = None

    """
    ENV
    """

    @property
    def deploy_env_hook(self) -> Optional[Callable[[Manifest], None]]:
        return self._deploy_env_hook

    @deploy_env_hook.setter
    def deploy_env_hook(self, func: Optional[Callable[[Manifest], None]]) -> None:
        self._deploy_env_hook = func

    @deploy_env_hook.deleter
    def deploy_env_hook(self) -> None:
        self._deploy_env_hook = None

    @property
    def destroy_env_hook(self) -> Optional[Callable[[Manifest], None]]:
        return self._destroy_env_hook

    @destroy_env_hook.setter
    def destroy_env_hook(self, func: Optional[Callable[[Manifest], None]]) -> None:
        self._destroy_env_hook = func

    @destroy_env_hook.deleter
    def destroy_env_hook(self) -> None:
        self._destroy_env_hook = None

    """
    TEAM
    """

    @property
    def deploy_team_hook(self) -> Optional[Callable[[Manifest, TeamManifest], None]]:
        return self._deploy_team_hook

    @deploy_team_hook.setter
    def deploy_team_hook(self, func: Optional[Callable[[Manifest, TeamManifest], None]]) -> None:
        self._deploy_team_hook = func

    @deploy_team_hook.deleter
    def deploy_team_hook(self) -> None:
        self._deploy_team_hook = None

    @property
    def destroy_team_hook(self) -> Optional[Callable[[Manifest, TeamManifest], None]]:
        return self._destroy_team_hook

    @destroy_team_hook.setter
    def destroy_team_hook(self, func: Optional[Callable[[Manifest, TeamManifest], None]]) -> None:
        self._destroy_team_hook = func

    @destroy_team_hook.deleter
    def destroy_team_hook(self) -> None:
        self._destroy_team_hook = None


def load_plugins(manifest: Manifest) -> None:
    for plugin in manifest.plugins:
        _logger.debug(f"Plugin load: {plugin.name}")
        PluginRegistry(name=plugin.name)
        importlib.import_module(plugin.name)
