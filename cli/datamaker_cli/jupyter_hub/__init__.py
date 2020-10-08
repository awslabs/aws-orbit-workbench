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

import sh

from datamaker_cli import DATAMAKER_CLI_ROOT
from datamaker_cli.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def deploy(manifest: Manifest) -> None:
    path = f"{DATAMAKER_CLI_ROOT}/../../images/jupyter-hub/"
    _logger.debug("path: %s", path)
    _logger.debug("Building JupyterHub Docker image")
    sh.sh("./build.sh", _cwd=path)
    _logger.debug("Deploying JupyterHub Docker image to ECR")
    sh.sh("./deploy.sh", manifest.name, manifest.region, _cwd=path)
    _logger.debug("JupyterHub deploy done")
