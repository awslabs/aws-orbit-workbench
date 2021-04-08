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
import os
from typing import Any, Dict, List, Optional, cast

from aws_orbit import ORBIT_CLI_ROOT, exceptions, sh
from aws_orbit.models.context import Context
from aws_orbit.services import s3


_logger: logging.Logger = logging.getLogger(__name__)

CHARTS_PATH = os.path.join(ORBIT_CLI_ROOT, "data", "charts")


def add_repo(repo: str, repo_location: str) -> None:
    _logger.debug("Adding Helm Repository: %s at %s", repo, repo_location)
    sh.run(f"helm repo add {repo} {repo_location}")


def init_env_repo(context: Context) -> str:
    repo_location = f"s3://{context.toolkit.s3_bucket}/helm/repository/{context.name}"
    if not s3.object_exists(bucket=cast(str, context.toolkit.s3_bucket), key=f"helm/repository/{context.name}/index.yaml"):
        _logger.debug("Initializing Env Helm Respository at %s", repo_location)
        sh.run(f"helm s3 init {repo_location}")
    else:
        _logger.debug("Skipping initialization of existing Env Helm Repository at %s", repo_location)

    return repo_location