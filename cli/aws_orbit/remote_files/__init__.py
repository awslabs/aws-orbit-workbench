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
import os
from enum import Enum
from typing import Callable, Tuple

from softwarelabs_remote_toolkit import create_output_dir, remotectl
from softwarelabs_remote_toolkit.remotectl import MODULE_IMPORTER, RemoteCtlConfig

from aws_orbit import ORBIT_CLI_ROOT
from aws_orbit.remote_files import build as build_image_module
from aws_orbit.remote_files import delete as delete_image_module
from aws_orbit.remote_files import deploy as deploy_module
from aws_orbit.remote_files import destroy as destroy_module

REMOTE_FUNC_TYPE = Callable[[Tuple[str, ...]], None]


class RemoteCommands(Enum):
    _deploy_image: REMOTE_FUNC_TYPE = deploy_module._deploy_image
    build_image: REMOTE_FUNC_TYPE = build_image_module.build_image
    delete_image: REMOTE_FUNC_TYPE = delete_image_module.delete_image
    deploy_credentials: REMOTE_FUNC_TYPE = deploy_module.deploy_credentials
    deploy_foundation: REMOTE_FUNC_TYPE = deploy_module.deploy_foundation
    deploy_env: REMOTE_FUNC_TYPE = deploy_module.deploy_env
    deploy_teams: REMOTE_FUNC_TYPE = deploy_module.deploy_teams
    destroy_teams: REMOTE_FUNC_TYPE = destroy_module.destroy_teams
    destroy_env: REMOTE_FUNC_TYPE = destroy_module.destroy_env
    destroy_foundation: REMOTE_FUNC_TYPE = destroy_module.destroy_foundation
    destroy_credentials: REMOTE_FUNC_TYPE = destroy_module.destroy_credentials


@remotectl.configure("orbit")
def configure(configuration: RemoteCtlConfig) -> None:
    configuration.python_modules = ["aws-orbit~=1.5.0.dev0", "softwarelabs-remote-toolkit~=0.1.0.dev0"]
    # configuration.local_modules = {
    #     "aws-orbit": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../cli")),
    #     "aws-orbit-sdk": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../sdk")),
    # }
    configuration.requirements_files = {
        "aws-orbit": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../requirements.txt")),
        "slrt": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../remote-requirements.txt"))
    }

