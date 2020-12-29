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

import collections
import logging
from pprint import pformat
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Union, cast

from aws_orbit import utils

if TYPE_CHECKING:
    from orbit_cli.manifest.team import MANIFEST_FILE_TEAM_TYPE, MANIFEST_TEAM_TYPE

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST_FILE_PLUGIN_TYPE = Dict[str, Union[str, Dict[str, Any]]]
MANIFEST_PLUGIN_TYPE = Dict[str, Union[str, Dict[str, Any]]]


def plugins_manifest_checks(team_name: str, plugins: List[MANIFEST_FILE_PLUGIN_TYPE]) -> None:
    _logger.debug("Plugin manifest content:\n%s", pformat(plugins))
    for p in plugins:
        if "id" not in p:
            raise RuntimeError(f"Plugin manifest content:\n{pformat(plugins)}")
    plugins_ids: List[str] = [cast(str, p["id"]) for p in plugins]
    repeated: Set[str] = set(i for i, count in collections.Counter(plugins_ids).items() if count > 1)
    if len(repeated) > 0:
        raise ValueError(f"Error parsing the plugins for team {team_name}. Repeated plugins IDs: {repeated}")


class PluginManifest:
    def __init__(self, plugin_id: str, module: str, parameters: Dict[str, Any], path: Optional[str] = None) -> None:
        self._plugin_id = plugin_id
        self._module = module
        self._path = path
        self._parameters = parameters

    def asdict_file(self) -> MANIFEST_FILE_PLUGIN_TYPE:
        return self.asdict()

    def asdict(self) -> MANIFEST_PLUGIN_TYPE:
        ret: MANIFEST_PLUGIN_TYPE = utils.replace_underscores(vars(self))
        ret["id"] = ret["plugin-id"]
        del ret["plugin-id"]
        return ret

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def module(self) -> str:
        return self._module

    @property
    def path(self) -> Optional[str]:
        return self._path

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters


def parse_plugins(team: Union["MANIFEST_FILE_TEAM_TYPE", "MANIFEST_TEAM_TYPE"]) -> List[PluginManifest]:
    if "plugins" in team:
        raw: List[MANIFEST_FILE_PLUGIN_TYPE] = cast(List[MANIFEST_FILE_PLUGIN_TYPE], team["plugins"])
        plugins_manifest_checks(team_name=cast(str, team["name"]), plugins=raw)
        return [
            PluginManifest(
                plugin_id=cast(str, p["id"]),
                module=cast(str, p.get("module", None)),
                path=cast(str, p["path"]),
                parameters=cast(Dict[str, Any], p.get("parameters", {})),
            )
            for p in raw
        ]
    return []
