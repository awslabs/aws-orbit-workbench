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
from pprint import pformat
from typing import List, Optional, Tuple

from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def _is_valid_image_file(file_path: str) -> bool:
    for word in ("/node_modules/", "/build/", "/.mypy_cache/", ".egg-info", "__pycache__"):
        if word in file_path:
            return False
    return True


def _list_files(path: str) -> List[str]:
    path = os.path.join(path, "**")
    return [f for f in glob.iglob(path, recursive=True) if os.path.isfile(f) and _is_valid_image_file(file_path=f)]


def _generate_dir(bundle_dir: str, dir: str, name: str) -> str:
    absolute_dir = os.path.realpath(dir)
    final_dir = os.path.join(bundle_dir, name)
    _logger.debug("absolute_dir: %s", absolute_dir)
    _logger.debug("final_dir: %s", final_dir)
    os.makedirs(final_dir, exist_ok=True)
    shutil.rmtree(final_dir)

    _logger.debug("Copying files to %s", final_dir)
    files: List[str] = _list_files(path=absolute_dir)
    if len(files) == 0:
        raise ValueError(f"{name} ({absolute_dir}) is empty!")
    for file in files:
        _logger.debug(f"***file={file}")
        relpath = os.path.relpath(file, absolute_dir)
        new_file = os.path.join(final_dir, relpath)
        _logger.debug("Copying file to %s", new_file)
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        _logger.debug("Copying file to %s", new_file)
        shutil.copy(src=file, dst=new_file)

    return final_dir


def generate_bundle(
    command_name: str,
    context: "Context",
    dirs: Optional[List[Tuple[str, str]]] = None,
) -> str:
    remote_dir = os.path.join(os.getcwd(), ".orbit.out", context.name, "remote", command_name)
    bundle_dir = os.path.join(remote_dir, "bundle")
    try:
        shutil.rmtree(bundle_dir)
    except FileNotFoundError:
        pass
    os.makedirs(bundle_dir, exist_ok=True)
    _logger.debug(f"generate_bundle dirs={dirs}")
    # Extra Directories
    if dirs is not None:
        for dir, name in dirs:
            _logger.debug(f"***dir={dir}:name={name}")
            _generate_dir(bundle_dir=bundle_dir, dir=dir, name=name)

    _logger.debug("bundle_dir: %s", bundle_dir)

    files = glob.glob(bundle_dir + "/**", recursive=True)
    _logger.debug("files:\n%s", pformat(files))

    shutil.make_archive(base_name=bundle_dir, format="zip", root_dir=remote_dir, base_dir="bundle")
    return bundle_dir + ".zip"
