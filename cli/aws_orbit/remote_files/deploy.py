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

import concurrent.futures
import logging
import os
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from aws_orbit import bundle, changeset, docker, plugins, remote, sh
from aws_orbit.manifest import Manifest, get_team_by_name
from aws_orbit.remote_files import cdk_toolkit, demo, eksctl, env, kubectl, teams
from aws_orbit.services import codebuild

if TYPE_CHECKING:
    from aws_orbit.changeset import TeamsChangeset
    from aws_orbit.manifest.team import TeamManifest

_logger: logging.Logger = logging.getLogger(__name__)


def _deploy_image(args: Tuple[str, ...]) -> None:
    _logger.debug("_deploy_image args: %s", args)
    filename: str = args[0]
    manifest: Manifest = Manifest(filename=filename, env=None, region=None)
    manifest.fetch_ssm()
    _logger.debug("manifest.name: %s", manifest.name)
    if len(args) == 2:
        image_name: str = args[1]
        script: Optional[str] = None
    elif len(args) == 3:
        image_name = args[1]
        script = args[2]
    else:
        raise ValueError("Unexpected number of values in args.")

    docker.login(manifest=manifest)
    _logger.debug("DockerHub and ECR Logged in")
    _logger.debug("Deploying the %s Docker image", image_name)

    if manifest.images.get(image_name, {"source": "code"}).get("source") == "code":
        _logger.debug("Building and deploy docker image from source...")
        path = os.path.join(os.path.dirname(manifest.filename_dir), image_name)
        _logger.debug("path: %s", path)
        if script is not None:
            sh.run(f"sh {script}", cwd=path)
        docker.deploy_image_from_source(manifest=manifest, dir=path, name=f"orbit-{manifest.name}-{image_name}")
    else:
        _logger.debug("Replicating docker iamge to ECR...")
        docker.replicate_image(
            manifest=manifest, image_name=image_name, deployed_name=f"orbit-{manifest.name}-{image_name}"
        )

    _logger.debug("Docker Image Deployed to ECR")


def _deploy_image_remotely(manifest: Manifest, name: str, bundle_path: str, buildspec: codebuild.SPEC_TYPE) -> None:
    _logger.debug("Deploying %s Docker Image remotely into ECR", name)
    remote.run(
        command_name=f"deploy_image-{name}",
        manifest=manifest,
        bundle_path=bundle_path,
        buildspec=buildspec,
        codebuild_log_callback=None,
        timeout=15,
    )
    _logger.debug("%s Docker Image deployed into ECR", name)


def _deploy_images_batch(manifest: Manifest, images: List[Tuple[str, Optional[str]]]) -> None:
    _logger.debug("images:\n%s", images)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(images)) as executor:
        futures: List[Future[Any]] = []

        for name, script in images:
            _logger.debug("name: %s | script: %s", name, script)

            path = os.path.join(os.path.dirname(manifest.filename_dir), name)
            _logger.debug("path: %s", path)

            if manifest.images.get(name, {"source": "code"}).get("source") == "code":
                dirs: List[Tuple[str, str]] = [(path, name)]
            else:
                dirs = []

            bundle_path = bundle.generate_bundle(
                command_name=f"deploy_image-{name}", manifest=manifest, dirs=dirs, plugins=False
            )
            _logger.debug("bundle_path: %s", bundle_path)
            script_str = "" if script is None else script
            buildspec = codebuild.generate_spec(
                manifest=manifest,
                plugins=False,
                cmds_build=[f"orbit remote --command _deploy_image ./conf/manifest.yaml {name} {script_str}"],
            )
            futures.append(executor.submit(_deploy_image_remotely, manifest, name, bundle_path, buildspec))

        for f in futures:
            f.result()


def deploy_images_remotely(manifest: Manifest) -> None:
    # First batch
    images: List[Tuple[str, Optional[str]]] = [
        ("jupyter-hub", None),
        ("jupyter-user", "build.sh"),
        ("landing-page", "build.sh"),
    ]
    _logger.debug("Building the first images batch")
    _deploy_images_batch(manifest=manifest, images=images)

    # Second Batch
    images = [
        ("jupyter-user-spark", None),
    ]
    if manifest.internet_accessible is False:
        images += [
            ("aws-efs-csi-driver", None),
            ("livenessprobe", None),
            ("csi-node-driver-registrar", None),
        ]
    _logger.debug("Building the second images batch")
    _deploy_images_batch(manifest=manifest, images=images)


def eval_teams_change(manifest: Manifest, teams_changeset: "TeamsChangeset") -> None:
    _logger.debug("Teams %s must be deleted.", teams_changeset.removed_teams_names)
    for name in teams_changeset.removed_teams_names:
        team_manifest: Optional["TeamManifest"] = get_team_by_name(teams=teams_changeset.old_teams, name=name)
        if team_manifest is None:
            raise RuntimeError(f"Team {name} not found!")
        _logger.debug("Destroying team %s", name)
        plugins.PLUGINS_REGISTRIES.destroy_team_plugins(manifest=manifest, team_manifest=team_manifest)
        kubectl.destroy_team(manifest=manifest, team_manifest=team_manifest)
        eksctl.destroy_team(manifest=manifest, team_manifest=team_manifest)
        teams.destroy(manifest=manifest, team_manifest=team_manifest)
        _logger.debug("Team %s destroyed", name)


def deploy_foundation(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    if len(args) != 1:
        raise ValueError("Unexpected number of values in args")
    filename: str = args[0]

    manifest: Manifest = Manifest(filename=filename, env=None, region=None)
    manifest.fillup()
    _logger.debug("Manifest loaded")
    docker.login(manifest=manifest)
    cdk_toolkit.deploy(manifest=manifest)
    _logger.debug("CDK Toolkit Stack deployed")
    demo.deploy(manifest=manifest)
    _logger.debug("Demo Stack deployed")


def deploy(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    filename: str = args[0]
    if len(args) == 3:
        skip_images_remote_flag: str = str(args[1])
        env_only: bool = args[2] == "env-stacks"
    else:
        raise ValueError("Unexpected number of values in args")

    manifest: Manifest = Manifest(filename=filename, env=None, region=None)
    manifest.fillup()
    _logger.debug("Manifest loaded")
    docker.login(manifest=manifest)
    _logger.debug("DockerHub and ECR Logged in")
    changes: changeset.Changeset = changeset.read_changeset_file(manifest=manifest, filename="changeset.json")
    _logger.debug(f"Changeset: {changes.asdict()}")
    _logger.debug("Changeset loaded")
    plugins.PLUGINS_REGISTRIES.load_plugins(
        manifest=manifest, plugin_changesets=changes.plugin_changesets, teams_changeset=changes.teams_changeset
    )
    _logger.debug("Plugins loaded")
    cdk_toolkit.deploy(manifest=manifest)
    _logger.debug("CDK Toolkit Stack deployed")
    demo.deploy(manifest=manifest)
    _logger.debug("Demo Stack deployed")
    manifest.fetch_network_data()
    env.deploy(
        manifest=manifest,
        add_images=[],
        remove_images=[],
        eks_system_masters_roles_changes=changes.eks_system_masters_roles_changeset,
    )
    _logger.debug("Env Stack deployed")
    if skip_images_remote_flag == "skip-images":
        _logger.debug("Docker images build skipped")
    else:
        deploy_images_remotely(manifest=manifest)
        _logger.debug("Docker Images deployed")
    eksctl.deploy_env(manifest=manifest, eks_system_masters_roles_changes=changes.eks_system_masters_roles_changeset)
    _logger.debug("EKS Environment Stack deployed")
    kubectl.deploy_env(manifest=manifest)
    _logger.debug("Kubernetes Environment components deployed")

    if not env_only:
        if changes.teams_changeset:
            eval_teams_change(manifest=manifest, teams_changeset=changes.teams_changeset)
        teams.deploy(manifest=manifest)
        _logger.debug("Team Stacks deployed")
        eksctl.deploy_teams(manifest=manifest)
        _logger.debug("EKS Team Stacks deployed")
        kubectl.deploy_teams(manifest=manifest, changes=changes.plugin_changesets)
        _logger.debug("Kubernetes Team components deployed")
    else:
        _logger.debug("Skipping Team Stacks")
