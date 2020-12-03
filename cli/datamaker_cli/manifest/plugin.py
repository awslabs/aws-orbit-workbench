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

from typing import Any, Dict, Optional, Union

from datamaker_cli import utils

MANIFEST_FILE_PLUGIN_TYPE = Dict[str, Union[str, Dict[str, Any]]]
MANIFEST_PLUGIN_TYPE = Dict[str, Union[str, Dict[str, Any]]]


class PluginManifest:
    def __init__(self, name: str, parameters: Dict[str, Any], path: Optional[str] = None) -> None:
        self._name = name
        self._path = path
        self._parameters = parameters

    def asdict_file(self) -> MANIFEST_FILE_PLUGIN_TYPE:
        return self.asdict()

    def asdict(self) -> MANIFEST_PLUGIN_TYPE:
        return utils.replace_underscores(vars(self))

    @property
    def name(self) -> str:
        return self._name

    @property
    def path(self) -> Optional[str]:
        return self._path

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters
