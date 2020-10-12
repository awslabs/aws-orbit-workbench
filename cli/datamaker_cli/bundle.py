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

import glob
import logging
import os
import shutil
from typing import List

from datamaker_cli import DATAMAKER_CLI_ROOT
from datamaker_cli.utils import path_from_filename

_logger: logging.Logger = logging.getLogger(__name__)


def _list_self_files() -> List[str]:
    return [f for f in glob.iglob(DATAMAKER_CLI_ROOT + "/**", recursive=True) if f.endswith((".py", ".yaml", ".typed"))]


def generate_self_dir(bundle_dir: str) -> str:
    cli_dir = os.path.join(bundle_dir, "cli")
    module_dir = os.path.join(cli_dir, "datamaker_cli")
    os.makedirs(module_dir, exist_ok=True)
    shutil.rmtree(cli_dir)

    _logger.debug("Copying files to %s", module_dir)
    for file in _list_self_files():
        relpath = os.path.relpath(file, DATAMAKER_CLI_ROOT)
        new_file = os.path.join(module_dir, relpath)
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        shutil.copy(src=file, dst=new_file)

    src_file = os.path.join(DATAMAKER_CLI_ROOT, "..", "setup.py")  # Only if manifest.dev is True
    dst_file = os.path.join(cli_dir, "setup.py")
    shutil.copy(src=src_file, dst=dst_file)
    return cli_dir


def generate_bundle(filename: str) -> str:
    filename_dir = path_from_filename(filename=filename)
    remote_dir = os.path.join(filename_dir, ".datamaker.out", "remote")
    bundle_dir = os.path.join(remote_dir, "bundle")
    os.makedirs(bundle_dir, exist_ok=True)
    shutil.rmtree(bundle_dir)
    generate_self_dir(bundle_dir=bundle_dir)

    shutil.copy(src=filename, dst=os.path.join(bundle_dir, "manifest.yaml"))  # manifest

    _logger.debug("bundle_dir: %s", bundle_dir)
    shutil.make_archive(base_name=bundle_dir, format="zip", root_dir=remote_dir, base_dir="bundle")
    return bundle_dir + ".zip"
