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

from enum import Enum
from typing import Callable, Tuple

from datamaker_cli.remote_files import deploy as deploy_module
from datamaker_cli.remote_files import deploy_image as deploy_image_module
from datamaker_cli.remote_files import destroy as destroy_module
from datamaker_cli.remote_files import destroy_image as destroy_image_module

REMOTE_FUNC_TYPE = Callable[[str, Tuple[str, ...]], None]


class RemoteCommands(Enum):
    deploy: REMOTE_FUNC_TYPE = deploy_module.deploy
    _deploy_image: REMOTE_FUNC_TYPE = deploy_module._deploy_image
    destroy: REMOTE_FUNC_TYPE = destroy_module.destroy
    deploy_image: REMOTE_FUNC_TYPE = deploy_image_module.deploy_image
    destroy_image: REMOTE_FUNC_TYPE = destroy_image_module.destroy_image
