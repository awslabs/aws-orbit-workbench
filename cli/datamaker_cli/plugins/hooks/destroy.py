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
from typing import Callable

from datamaker_cli.manifest import Manifest, TeamManifest
from datamaker_cli.plugins import PLUGINS_REGISTRY
from datamaker_cli.utils import extract_plugin_name

_logger: logging.Logger = logging.getLogger(__name__)


def demo(func: Callable[[Manifest], None]) -> Callable[[Manifest], None]:
    PLUGINS_REGISTRY[extract_plugin_name(func=func)].destroy_demo_hook = func
    return func


def env(func: Callable[[Manifest], None]) -> Callable[[Manifest], None]:
    PLUGINS_REGISTRY[extract_plugin_name(func=func)].destroy_env_hook = func
    return func


def team(func: Callable[[Manifest, TeamManifest], None]) -> Callable[[Manifest, TeamManifest], None]:
    PLUGINS_REGISTRY[extract_plugin_name(func=func)].destroy_team_hook = func
    return func
