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
from typing import List, Optional, Tuple

from datamaker_cli import DATAMAKER_CLI_ROOT
from datamaker_cli.changeset import Changeset
from datamaker_cli.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def _list_self_files() -> List[str]:
    path = os.path.join(DATAMAKER_CLI_ROOT, "**")
    extensions = (".py", ".yaml", ".typed", ".json")
    return [f for f in glob.iglob(path, recursive=True) if os.path.isfile(f) and f.endswith(extensions)]


def _is_valid_image_file(file_path: str) -> bool:
    for word in ("/node_modules/", "/build/", "/.mypy_cache/"):
        if word in file_path:
            return False
    return True


def _list_files(path: str) -> List[str]:
    path = os.path.join(path, "**")
    return [f for f in glob.iglob(path, recursive=True) if os.path.isfile(f) and _is_valid_image_file(file_path=f)]


def _generate_self_dir(bundle_dir: str) -> str:
    cli_dir = os.path.join(bundle_dir, "cli")
    module_dir = os.path.join(cli_dir, "datamaker_cli")
    os.makedirs(module_dir, exist_ok=True)
    shutil.rmtree(cli_dir)

    _logger.debug("Copying files to %s", module_dir)
    for file in _list_self_files():
        relpath = os.path.relpath(file, DATAMAKER_CLI_ROOT)
        new_file = os.path.join(module_dir, relpath)
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        _logger.debug("Copying file to %s", new_file)
        shutil.copy(src=file, dst=new_file)

    for filename in ("setup.py", "VERSION", "requirements.txt"):
        src_file = os.path.join(DATAMAKER_CLI_ROOT, "..", filename)
        dst_file = os.path.join(cli_dir, filename)
        shutil.copy(src=src_file, dst=dst_file)

    return cli_dir


def _generate_dir(bundle_dir: str, dir: str, name: str) -> str:
    absolute_dir = os.path.realpath(dir)
    image_dir = os.path.join(bundle_dir, name)
    _logger.debug("absolute_dir: %s", absolute_dir)
    _logger.debug("image_dir: %s", image_dir)
    os.makedirs(image_dir, exist_ok=True)
    shutil.rmtree(image_dir)

    _logger.debug("Copying files to %s", image_dir)
    files: List[str] = _list_files(path=absolute_dir)
    for file in files:
        relpath = os.path.relpath(file, absolute_dir)
        new_file = os.path.join(image_dir, relpath)
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        _logger.debug("Copying file to %s", new_file)
        shutil.copy(src=file, dst=new_file)

    return image_dir


def generate_bundle(
    command_name: str,
    manifest: Manifest,
    dirs: Optional[List[Tuple[str, str]]] = None,
    changeset: Optional[Changeset] = None,
) -> str:
    remote_dir = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, "remote", command_name)
    bundle_dir = os.path.join(remote_dir, "bundle")
    try:
        shutil.rmtree(bundle_dir)
    except FileNotFoundError:
        pass

    # manifest
    bundled_manifest_path = os.path.join(bundle_dir, "manifest.yaml")
    os.makedirs(bundle_dir, exist_ok=True)
    shutil.copy(src=manifest.filename, dst=bundled_manifest_path)

    # changeset
    if changeset is not None:
        bundled_changeset_path = os.path.join(bundle_dir, "changeset.json")
        changeset.write_changeset_file(filename=bundled_changeset_path)

    # DataMaker CLI Source
    if manifest.dev:
        _generate_self_dir(bundle_dir=bundle_dir)

    # Plugins
    for plugin in manifest.plugins:
        if plugin.path:
            _generate_dir(bundle_dir=bundle_dir, dir=plugin.path, name=plugin.name)

    # Extra Directories
    if dirs is not None:
        for dir, name in dirs:
            _generate_dir(bundle_dir=bundle_dir, dir=dir, name=name)

    _logger.debug("bundle_dir: %s", bundle_dir)
    shutil.make_archive(base_name=bundle_dir, format="zip", root_dir=remote_dir, base_dir="bundle")
    return bundle_dir + ".zip"
