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

import logging
from typing import Any, Callable, Dict, List

from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.plugins import PLUGINS_REGISTRIES

_logger: logging.Logger = logging.getLogger(__name__)


def deploy(
    func: Callable[[Manifest, TeamManifest, Dict[str, Any]], None]
) -> Callable[[Manifest, TeamManifest, Dict[str, Any]], None]:
    PLUGINS_REGISTRIES.add_hook(hook_name="deploy_hook", func=func)
    return func


def destroy(
    func: Callable[[Manifest, TeamManifest, Dict[str, Any]], None]
) -> Callable[[Manifest, TeamManifest, Dict[str, Any]], None]:
    PLUGINS_REGISTRIES.add_hook(hook_name="destroy_hook", func=func)
    return func


def dockerfile_injection(
    func: Callable[[Manifest, TeamManifest, Dict[str, Any]], List[str]]
) -> Callable[[Manifest, TeamManifest, Dict[str, Any]], List[str]]:
    PLUGINS_REGISTRIES.add_hook(hook_name="dockerfile_injection_hook", func=func)
    return func


def bootstrap_injection(
    func: Callable[[Manifest, TeamManifest, Dict[str, Any]], str]
) -> Callable[[Manifest, TeamManifest, Dict[str, Any]], str]:
    PLUGINS_REGISTRIES.add_hook(hook_name="bootstrap_injection_hook", func=func)
    return func
