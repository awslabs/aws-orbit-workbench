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
from typing import Any, List, Optional, Tuple

from datamaker_cli import bundle, changeset, docker, plugins, remote, sh
from datamaker_cli.manifest import Manifest
from datamaker_cli.remote_files import cdk_toolkit, demo, eksctl, env, kubectl, teams
from datamaker_cli.services import codebuild

_logger: logging.Logger = logging.getLogger(__name__)


def _deploy_image(filename: str, args: Tuple[str, ...]) -> None:
    manifest: Manifest = Manifest(filename=filename)
    manifest.fetch_ssm()
    _logger.debug("manifest.name: %s", manifest.name)
    _logger.debug("args: %s", args)
    if len(args) == 1:
        image_name: str = args[1]
        script: Optional[str] = None
    elif len(args) == 2:
        image_name = args[1]
        script = args[2]
    else:
        raise ValueError("Unexpected number of values in args.")

    path = os.path.join(manifest.filename_dir, image_name)
    _logger.debug("path: %s", path)
    _logger.debug("Deploying the %s Docker image", image_name)
    if manifest.images.get(image_name, {"source": "code"}).get("source") == "code":
        if script is not None:
            sh.run(f"sh {script}", cwd=path)
        docker.deploy_dynamic_image(manifest=manifest, dir=path, name=f"datamaker-{manifest.name}-{image_name}")
    else:
        docker.deploy(
            manifest=manifest, dir=path, image_name=image_name, deployed_name=f"datamaker-{manifest.name}-{image_name}"
        )
    _logger.debug("Docker Image Deployed to ECR")


def deploy_image_remotely(manifest: Manifest, name: str, bundle_path: str, buildspec: codebuild.SPEC_TYPE) -> None:
    _logger.debug("Deploying %s Docker Image remotely into ECR", name)
    remote.run(
        command_name=f"deploy_image-{name}",
        manifest=manifest,
        bundle_path=bundle_path,
        buildspec=buildspec,
        codebuild_log_callback=None,
        timeout=10,
    )
    _logger.debug("%s Docker Image deployed into ECR", name)


def deploy_images_remotely(manifest: Manifest) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures: List[Future[Any]] = []

        for name, script in (
            ("jupyter-hub", None),
            ("jupyter-user", None),
            ("landing-page", "build.sh"),
        ):
            _logger.debug("name: %s | script: %s", name, script)
            path = os.path.join(manifest.filename_dir, name)
            _logger.debug("path: %s", path)
            bundle_path = bundle.generate_bundle(
                command_name=f"deploy_image-{name}",
                manifest=manifest,
                dirs=[(path, name)],
            )
            _logger.debug("bundle_path: %s", bundle_path)
            script_str = "" if script is None else script
            buildspec = codebuild.generate_spec(
                manifest=manifest,
                plugins=False,
                cmds_build=[f"datamaker remote --command _deploy_image {name} {script_str}"],
            )
            futures.append(executor.submit(deploy_image_remotely, manifest, name, bundle_path, buildspec))

        for f in futures:
            f.result()


def deploy(filename: str, args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    if len(args) == 1:
        skip_images_remote_flag: str = str(args[0])
    else:
        raise ValueError("Unexpected number of values in args.")

    manifest: Manifest = Manifest(filename=filename)
    manifest.fillup()
    _logger.debug("Manifest loaded")
    plugins.PLUGINS_REGISTRIES.load_plugins(manifest=manifest)
    _logger.debug("Plugins loaded")
    changes: changeset.Changeset = changeset.read_changeset_file(
        filename=os.path.join(manifest.filename_dir, "changeset.json")
    )
    _logger.debug(f"Changeset: {changes.asdict()}")
    _logger.debug("Changeset loaded")
    cdk_toolkit.deploy(manifest=manifest)
    _logger.debug("CDK Toolkit Stack deployed")
    demo.deploy(manifest=manifest)
    _logger.debug("Demo Stack deployed")
    manifest.fetch_network_data()
    env.deploy(
        manifest=manifest,
        add_images=[],
        remove_images=[],
    )
    _logger.debug("Env Stack deployed")
    if skip_images_remote_flag == "skip-images":
        _logger.debug("Docker images build skipped")
    else:
        deploy_images_remotely(manifest=manifest)
        _logger.debug("Docker Images deployed")
    teams.deploy(manifest=manifest)
    _logger.debug("Teams Stacks deployed")
    eksctl.deploy(manifest=manifest)
    _logger.debug("EKS Stack deployed")
    kubectl.deploy(manifest=manifest)
    _logger.debug("Kubernetes components deployed")
