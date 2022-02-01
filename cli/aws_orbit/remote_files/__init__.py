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

from aws_codeseeder import LOGGER, codeseeder
from aws_codeseeder.codeseeder import CodeSeederConfig

from aws_orbit import ORBIT_CLI_ROOT
from aws_orbit.remote_files import delete as delete_image_module
from aws_orbit.remote_files import deploy as deploy_module
from aws_orbit.remote_files import destroy as destroy_module

REMOTE_FUNC_TYPE = Callable[[Tuple[str, ...]], None]


class RemoteCommands(Enum):
    delete_image = delete_image_module.delete_image
    deploy_credentials = deploy_module.deploy_credentials
    deploy_foundation = deploy_module.deploy_foundation
    deploy_env = deploy_module.deploy_env
    deploy_teams = deploy_module.deploy_teams
    destroy_teams = destroy_module.destroy_teams
    destroy_env = destroy_module.destroy_env
    destroy_foundation = destroy_module.destroy_foundation
    destroy_credentials = destroy_module.destroy_credentials


@codeseeder.configure("orbit")
def configure(configuration: CodeSeederConfig) -> None:
    LOGGER.debug("ORBIT_CLI_ROOT %s", ORBIT_CLI_ROOT)
    configuration.timeout = 240
    configuration.codebuild_image = "public.ecr.aws/v3o4w1g6/aws-codeseeder/code-build-base:2.0.0"
    configuration.pre_build_commands = [
        (
            "nohup /usr/local/bin/dockerd --host=unix:///var/run/docker.sock"
            " --host=tcp://127.0.0.1:2375 --storage-driver=overlay2&"
        ),
        'timeout 15 sh -c "until docker info; do echo .; sleep 1; done"',
    ]

    if "yes" != os.environ.get("JUPYTER_ENABLE_LAB", "no").lower():
        LOGGER.debug("Using src code references in toolkit")
        configuration.local_modules = {
            "aws-orbit": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../cli")),
        }
        configuration.requirements_files = {
            "aws-orbit": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../requirements.txt")),
            "codeseeder": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../remote-requirements.txt")),
        }
        configuration.dirs = {
            "aws-orbit-sdk": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../sdk")),
            "aws-orbit": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../cli")),
        }
    else:
        LOGGER.debug("Using path on Images for toolkit")
        configuration.local_modules = {
            "aws-orbit": "/opt/orbit/aws-orbit_jupyter-user/aws-orbit",
        }
        configuration.requirements_files = {
            "aws-orbit": "/opt/orbit/aws-orbit_jupyter-user/aws-orbit/requirements.txt",
            "codeseeder": "/opt/orbit/aws-orbit_jupyter-user/aws-orbit/remote-requirements.txt",
        }
        configuration.dirs = {
            "aws-orbit-sdk": "/opt/orbit/aws-orbit_jupyter-user/aws-orbit-sdk",
            "jupyterlab_orbit": "/opt/orbit/aws-orbit_jupyter-user/jupyterlab_orbit",
        }
