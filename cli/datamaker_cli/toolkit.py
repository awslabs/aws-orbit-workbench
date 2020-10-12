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
import shutil

from datamaker_cli import DATAMAKER_CLI_ROOT
from datamaker_cli.manifest import Manifest
from datamaker_cli.utils import path_from_filename

_logger: logging.Logger = logging.getLogger(__name__)

FILENAME = "template.yaml"
MODEL_FILENAME = os.path.join(DATAMAKER_CLI_ROOT, "data", "toolkit", FILENAME)


def synth(filename: str, manifest: Manifest) -> str:
    filename_dir = path_from_filename(filename=filename)
    outdir = os.path.join(filename_dir, ".datamaker.out", manifest.name, "toolkit")
    output_filename = os.path.join(outdir, FILENAME)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)

    _logger.debug("Reading %s", MODEL_FILENAME)
    with open(MODEL_FILENAME, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        env_name=manifest.name, account_id=manifest.account_id, region=manifest.region
    )
    _logger.debug("Writing %s", output_filename)
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, "w") as file:
        file.write(content)

    return output_filename
