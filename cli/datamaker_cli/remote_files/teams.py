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
from typing import TYPE_CHECKING, List, Optional

from datamaker_cli import cdk, docker, plugins
from datamaker_cli.services import cfn, s3

if TYPE_CHECKING:
    from datamaker_cli.manifest import Manifest
    from datamaker_cli.manifest.team import TeamManifest

_logger: logging.Logger = logging.getLogger(__name__)


def _create_dockefile(manifest: "Manifest", team_manifest: "TeamManifest") -> Optional[str]:
    cmds: List[str] = []
    for plugin in team_manifest.plugins:
        hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
            manifest=manifest,
            team_name=team_manifest.name,
            plugin_name=plugin.name,
            hook_name="dockerfile_injection_hook",
        )
        if hook is not None:
            plugin_cmds = hook(manifest, team_manifest)
            if plugin_cmds is not None:
                cmds += [f"# Commands for {plugin.name} plugin"] + plugin_cmds
    _logger.debug("cmds: %s", cmds)
    if cmds:
        base_image: str = f"FROM {team_manifest.base_image_address}"
        _logger.debug("base_image: %s", base_image)
        cmds = [base_image] + cmds
        outdir = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, team_manifest.name, "image")
        output_filename = os.path.join(outdir, "Dockerfile")
        os.makedirs(outdir, exist_ok=True)
        shutil.rmtree(outdir)
        _logger.debug("Writing %s", output_filename)
        os.makedirs(outdir, exist_ok=True)
        content: str = "\n".join(cmds)
        _logger.debug("content:\n%s", content)
        with open(output_filename, "w") as file:
            file.write(content)
        return outdir
    return None


def _deploy_team_image(manifest: "Manifest", team_manifest: "TeamManifest") -> None:
    image_dir: Optional[str] = _create_dockefile(manifest=manifest, team_manifest=team_manifest)
    if image_dir is not None:
        image_name: str = f"datamaker-{manifest.name}-{team_manifest.name}"
        _logger.debug("Deploying the %s Docker image", image_name)
        docker.deploy_dynamic_image(manifest=manifest, dir=image_dir, name=image_name)
        _logger.debug("Docker Image Deployed to ECR")


def deploy(manifest: "Manifest") -> None:
    for team_manifest in manifest.teams:
        cdk.deploy(
            manifest=manifest,
            stack_name=team_manifest.stack_name,
            app_filename="team.py",
            args=[manifest.filename, team_manifest.name],
        )
        manifest.fetch_ssm()
        _deploy_team_image(manifest=manifest, team_manifest=team_manifest)
    plugins.PLUGINS_REGISTRIES.deploy_teams(manifest=manifest)


def destroy(manifest: "Manifest") -> None:
    plugins.PLUGINS_REGISTRIES.destroy_teams(manifest=manifest)
    for team_manifest in manifest.teams:
        _logger.debug("Stack name: %s", team_manifest.stack_name)
        if cfn.does_stack_exist(manifest=manifest, stack_name=manifest.toolkit_stack_name):
            if team_manifest.scratch_bucket is not None:
                try:
                    s3.delete_bucket(manifest=manifest, bucket=team_manifest.scratch_bucket)
                except Exception as ex:
                    _logger.debug("Skipping Team scratch bucket deletion. Cause: %s", ex)
                if cfn.does_stack_exist(manifest=manifest, stack_name=team_manifest.stack_name):
                    cdk.destroy(
                        manifest=manifest,
                        stack_name=team_manifest.stack_name,
                        app_filename="team.py",
                        args=[manifest.filename, team_manifest.name],
                    )
