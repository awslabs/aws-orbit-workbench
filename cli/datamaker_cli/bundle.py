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
    for word in ("/node_modules/", "/build/", "/.mypy_cache/", "yarn.lock", ".egg-info", "__pycache__"):
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
        relpath = os.path.relpath(file, absolute_dir)
        new_file = os.path.join(final_dir, relpath)
        os.makedirs(os.path.dirname(new_file), exist_ok=True)
        _logger.debug("Copying file to %s", new_file)
        shutil.copy(src=file, dst=new_file)

    return final_dir


def generate_bundle(
    command_name: str,
    manifest: Manifest,
    dirs: Optional[List[Tuple[str, str]]] = None,
    changeset: Optional[Changeset] = None,
    plugins: bool = True,
) -> str:
    conf_dir = os.path.dirname(os.path.abspath(manifest.filename))
    remote_dir = os.path.join(os.path.dirname(conf_dir), ".datamaker.out", manifest.name, "remote", command_name)
    bundle_dir = os.path.join(remote_dir, "bundle")
    try:
        shutil.rmtree(bundle_dir)
    except FileNotFoundError:
        pass

    # manifest
    bundled_manifest_path = os.path.join(bundle_dir, "conf", "manifest.yaml")
    bundled_manifest_path_conf = os.path.join(bundle_dir, "conf")
    os.makedirs(bundle_dir, exist_ok=True)

    _logger.debug(f"copy conf_dir={conf_dir} to {bundled_manifest_path_conf}")
    shutil.copytree(src=conf_dir, dst=bundled_manifest_path_conf)
    _logger.debug(f"copy manifest file={manifest.filename} to {bundled_manifest_path_conf}")
    shutil.copy(src=manifest.filename, dst=bundled_manifest_path)

    # changeset
    if changeset is not None:
        bundled_changeset_path = os.path.join(bundle_dir, "changeset.json")
        changeset.write_changeset_file(filename=bundled_changeset_path)

    # DataMaker CLI Source
    if manifest.dev:
        _generate_self_dir(bundle_dir=bundle_dir)

    # Plugins
    if plugins:
        for team_manifest in manifest.teams:
            plugin_bundle_dir = os.path.join(bundle_dir, team_manifest.name)
            _logger.debug("plugin_bundle_dir: %s", plugin_bundle_dir)
            for plugin in team_manifest.plugins:
                if plugin.path is not None and plugin.module is not None:
                    _logger.debug("Bundling plugin %s (%s)...", plugin.plugin_id, plugin.path)
                    _generate_dir(bundle_dir=plugin_bundle_dir, dir=plugin.path, name=plugin.module)
        if changeset is not None:
            for plugin_changeset in changeset.plugin_changesets:
                plugin_bundle_dir = os.path.join(bundle_dir, plugin_changeset.team_name)
                for plugin_name, plugin_path in plugin_changeset.old_paths.items():
                    module: str = plugin_changeset.old_modules[plugin_name]
                    if plugin_name not in plugin_changeset.new and module is not None:
                        _logger.debug("Changest - Bundling plugin %s (%s)...", plugin_name, plugin_path)
                        _generate_dir(bundle_dir=plugin_bundle_dir, dir=plugin_path, name=module)

    # Extra Directories
    if dirs is not None:
        for dir, name in dirs:
            _generate_dir(bundle_dir=bundle_dir, dir=dir, name=name)

    _logger.debug("bundle_dir: %s", bundle_dir)
    shutil.make_archive(base_name=bundle_dir, format="zip", root_dir=remote_dir, base_dir="bundle")
    return bundle_dir + ".zip"
