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
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, cast

from aws_orbit import bundle, docker, plugins, remote, sh
from aws_orbit.models.changeset import load_changeset_from_ssm
from aws_orbit.models.context import load_context_from_ssm
from aws_orbit.remote_files import cdk_toolkit, demo, eksctl, env, kubectl, teams
from aws_orbit.services import codebuild

if TYPE_CHECKING:
    from aws_orbit.models.changeset import Changeset
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def _deploy_image(args: Tuple[str, ...]) -> None:
    _logger.debug("_deploy_image args: %s", args)
    if len(args) < 4:
        raise ValueError("Unexpected number of values in args.")
    env: str = args[0]
    image_name: str = args[1]
    dir: str = args[2]
    script: Optional[str] = args[3] if args[3] != "NO_SCRIPT" else None
    build_args = args[4:]

    context: "Context" = load_context_from_ssm(env_name=env)
    _logger.debug("manifest.name: %s", context.name)

    docker.login(context=context)
    _logger.debug("DockerHub and ECR Logged in")
    _logger.debug("Deploying the %s Docker image", image_name)

    if getattr(context.images, image_name.replace("-", "_")).source == "code":
        _logger.debug("Building and deploy docker image from source...")
        path = os.path.join(os.getcwd(), dir)
        _logger.debug("path: %s", path)
        if script is not None:
            sh.run(f"sh {script}", cwd=path)
        docker.deploy_image_from_source(
            context=context,
            dir=path,
            name=f"orbit-{context.name}-{image_name}",
            build_args=cast(Optional[List[str]], build_args),
        )
    else:
        _logger.debug("Replicating docker iamge to ECR...")
        docker.replicate_image(
            context=context, image_name=image_name, deployed_name=f"orbit-{context.name}-{image_name}"
        )

    _logger.debug("Docker Image Deployed to ECR")


def _deploy_image_remotely(context: "Context", name: str, bundle_path: str, buildspec: codebuild.SPEC_TYPE) -> None:
    _logger.debug("Deploying %s Docker Image remotely into ECR", name)
    remote.run(
        command_name=f"deploy_image-{name}",
        context=context,
        bundle_path=bundle_path,
        buildspec=buildspec,
        codebuild_log_callback=None,
        timeout=30,
    )
    _logger.debug("%s Docker Image deployed into ECR", name)


def _deploy_images_batch(context: "Context", images: List[Tuple[str, Optional[str], Optional[str], List[str]]]) -> None:
    _logger.debug("images:\n%s", images)

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(images)) as executor:
        futures: List[Future[Any]] = []
        name: str = ""
        dir: Optional[str] = None
        script: Optional[str] = None
        build_args: List[str] = []

        for name, dir, script, build_args in images:
            _logger.debug("name: %s | script: %s", name, script)

            path = os.path.join(os.getcwd(), name)
            _logger.debug("path: %s", path)

            if getattr(context.images, name.replace("-", "_")).source == "code":
                dirs: List[Tuple[str, str]] = [(path, cast(str, dir))]
            else:
                dirs = []

            bundle_path = bundle.generate_bundle(
                command_name=f"deploy_image-{name}", context=context, dirs=dirs, plugins=False
            )
            _logger.debug("bundle_path: %s", bundle_path)
            script_str = "NO_SCRIPT" if script is None else script
            build_args = [] if build_args is None else build_args
            buildspec = codebuild.generate_spec(
                context=context,
                plugins=False,
                cmds_build=[
                    "orbit remote --command _deploy_image "
                    f"{context.name} {name} {dir} {script_str} {' '.join(build_args)}"
                ],
            )
            futures.append(executor.submit(_deploy_image_remotely, context, name, bundle_path, buildspec))

        for f in futures:
            f.result()


def deploy_images_remotely(context: "Context") -> None:
    # First batch
    images: List[Tuple[str, Optional[str], Optional[str], List[str]]] = [
        ("jupyter-hub", "jupyter-hub", None, []),
        ("jupyter-user", "jupyter-user", "build.sh", []),
        ("landing-page", "landing-page", "build.sh", []),
        ("gpu-jupyter-user", "jupyter-user", "build.sh", ["BASE_IMAGE=cschranz/gpu-jupyter"]),
    ]
    _logger.debug("Building the first images batch")
    _deploy_images_batch(context=context, images=images)

    # Second Batch
    images = [
        ("jupyter-user-spark", "jupyter-user-spark", None, []),
    ]
    if context.networking.data.internet_accessible is False:
        images += [
            ("aws-efs-csi-driver", None, None, []),
            ("livenessprobe", None, None, []),
            ("csi-node-driver-registrar", None, None, []),
        ]
    _logger.debug("Building the second images batch")
    _deploy_images_batch(context=context, images=images)


def deploy_foundation(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    if len(args) != 1:
        raise ValueError("Unexpected number of values in args")
    env_name: str = args[0]
    context: "Context" = load_context_from_ssm(env_name=env_name)
    _logger.debug("Context loaded.")
    docker.login(context=context)
    _logger.debug("DockerHub and ECR Logged in")
    cdk_toolkit.deploy(context=context)
    _logger.debug("CDK Toolkit Stack deployed")
    demo.deploy(context=context)
    _logger.debug("Demo Stack deployed")


def deploy(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    env_name: str = args[0]
    if len(args) == 3:
        skip_images_remote_flag: str = str(args[1])
        env_only: bool = args[2] == "env-stacks"
    else:
        raise ValueError("Unexpected number of values in args")

    context: "Context" = load_context_from_ssm(env_name=env_name)
    _logger.debug("Context loaded.")
    changeset: Optional["Changeset"] = load_changeset_from_ssm(env_name=env_name)
    _logger.debug("Changeset loaded.")

    if changeset:
        plugins.PLUGINS_REGISTRIES.load_plugins(
            context=context, plugin_changesets=changeset.plugin_changesets, teams_changeset=changeset.teams_changeset
        )
        _logger.debug("Plugins loaded")

    docker.login(context=context)
    _logger.debug("DockerHub and ECR Logged in")
    cdk_toolkit.deploy(context=context)
    _logger.debug("CDK Toolkit Stack deployed")
    demo.deploy(context=context)
    _logger.debug("Demo Stack deployed")
    env.deploy(
        context=context,
        add_images=[],
        remove_images=[],
        eks_system_masters_roles_changes=changeset.eks_system_masters_roles_changeset if changeset else None,
    )
    _logger.debug("Env Stack deployed")
    if skip_images_remote_flag == "skip-images":
        _logger.debug("Docker images build skipped")
    else:
        deploy_images_remotely(context=context)
        _logger.debug("Docker Images deployed")
    eksctl.deploy_env(
        context=context,
        changeset=changeset,
    )
    _logger.debug("EKS Environment Stack deployed")
    kubectl.deploy_env(context=context)
    _logger.debug("Kubernetes Environment components deployed")

    if not env_only:
        teams.deploy(context=context, teams_changeset=changeset.teams_changeset if changeset else None)
        _logger.debug("Team Stacks deployed")
        eksctl.deploy_teams(context=context)
        _logger.debug("EKS Team Stacks deployed")
        kubectl.deploy_teams(context=context, changes=changeset.plugin_changesets if changeset else [])
        _logger.debug("Kubernetes Team components deployed")
    else:
        _logger.debug("Skipping Team Stacks")
