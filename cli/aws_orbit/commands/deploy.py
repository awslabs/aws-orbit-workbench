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

import json
import logging
import os
import random
import string
from typing import List, Optional, Tuple, cast

from aws_orbit import bundle, remote, toolkit
from aws_orbit.messages import MessagesContext, stylize
from aws_orbit.models.changeset import Changeset, dump_changeset_to_str, extract_changeset
from aws_orbit.models.context import Context, ContextSerDe, FoundationContext
from aws_orbit.models.manifest import (
    DataNetworkingManifest,
    FoundationManifest,
    FrontendNetworkingManifest,
    ImagesManifest,
    Manifest,
    ManifestSerDe,
    NetworkingManifest,
    manifest_validations,
)
from aws_orbit.services import cfn, codebuild
from aws_orbit.services import cognito as orbit_cognito
from aws_orbit.services import kms, ssm

_logger: logging.Logger = logging.getLogger(__name__)


def _get_images_dirs(context: "Context", manifest_filename: str, skip_images: bool) -> List[Tuple[str, str]]:
    if skip_images:
        dirs: List[Tuple[str, str]] = []
    else:
        refdir: str = os.path.dirname(os.path.abspath(manifest_filename))
        _logger.debug("refdir: %s", refdir)
        dirs = [
            (os.path.join(refdir, getattr(context.images, name).path), name.replace("_", "-"))
            for name in context.images.names
            if getattr(context.images, name).get_source(account_id=context.account_id, region=context.region) == "code"
        ]
        _logger.debug("dirs: %s", dirs)
    return dirs


def _get_config_dirs(context: "Context", manifest_filename: str) -> List[Tuple[str, str]]:
    manifest_dir: str = os.path.dirname(os.path.abspath(manifest_filename))
    _logger.debug("manrefdir: %s", manifest_dir)
    dirs = [(manifest_dir, "plugins")]
    _logger.debug("dirs: %s", dirs)
    return dirs


def _deploy_toolkit(
    context: "Context",
    top_level: str = "orbit",
) -> None:
    stack_exist: bool = cfn.does_stack_exist(stack_name=context.toolkit.stack_name)
    if not stack_exist:
        context.toolkit.deploy_id = "".join(random.choice(string.ascii_lowercase) for i in range(6))
    _logger.debug("context.toolkit.deploy_id: %s", context.toolkit.deploy_id)
    template_filename: str = toolkit.synth(context=context, top_level=top_level)
    cfn.deploy_template(
        stack_name=context.toolkit.stack_name, filename=template_filename, env_tag=context.env_tag, s3_bucket=None
    )
    ContextSerDe.fetch_toolkit_data(context=context)
    ContextSerDe.dump_context_to_ssm(context=context)


def deploy_toolkit(
    filename: str,
    debug: bool,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(10)

        manifest: "Manifest" = ManifestSerDe.load_manifest_from_file(filename=filename, type=Manifest)
        msg_ctx.info(f"Manifest loaded: {filename}")
        msg_ctx.progress(25)

        context: "Context" = ContextSerDe.load_context_from_manifest(manifest=manifest)

        msg_ctx.info("Current Context loaded")
        msg_ctx.progress(45)

        _deploy_toolkit(
            context=context,
        )
        msg_ctx.info("Toolkit deployed")
        msg_ctx.progress(100)


def deploy_credentials(filename: str, username: str, password: str, registry: str, debug: bool) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        manifest: "Manifest" = ManifestSerDe.load_manifest_from_file(filename=filename, type=Manifest)
        msg_ctx.info(f"Manifest loaded: {filename}")
        msg_ctx.progress(3)

        context_parameter_name: str = f"/orbit/{manifest.name}/context"
        if not ssm.does_parameter_exist(name=context_parameter_name):
            msg_ctx.error(f"Orbit Environment {manifest.name} cannot be found in the current account and region.")
            return

        context: "Context" = ContextSerDe.load_context_from_manifest(manifest=manifest)
        msg_ctx.info("Current Context loaded")
        msg_ctx.progress(4)

        bundle_path = bundle.generate_bundle(
            command_name="deploy",
            context=context,
        )
        msg_ctx.progress(11)

        msg_ctx.info("Encrypting credentials with Toolkit KMS Key")
        ciphertext = kms.encrypt(
            context=context, plaintext=json.dumps({registry: {"username": username, "password": password}})
        )
        msg_ctx.progress(20)

        msg_ctx.info("Starting Remote CodeBuild to deploy credentials")
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=True,
            cmds_build=[f"orbit remote --command deploy_credentials {context.name} '{ciphertext}'"],
        )
        remote.run(
            command_name="deploy",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=10,
            overrides={"environmentVariablesOverride": [{"name": "CREDENTIALS_CIPHERTEXT", "value": ciphertext}]},
        )
        msg_ctx.info("Registry Credentials deployed")
        msg_ctx.progress(98)

        if cfn.does_stack_exist(stack_name=context.env_stack_name):
            context = ContextSerDe.load_context_from_ssm(env_name=manifest.name, type=Context)
            msg_ctx.info(f"Context updated: {filename}")
        msg_ctx.progress(100)


def deploy_foundation(
    filename: Optional[str] = None,
    name: Optional[str] = None,
    debug: bool = False,
    internet_accessibility: bool = True,
    codeartifact_domain: Optional[str] = None,
    codeartifact_repository: Optional[str] = None,
    ssl_cert_arn: Optional[str] = None,
    custom_domain_name: Optional[str] = None,
    max_availability_zones: Optional[int] = None,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        if filename:
            manifest: "FoundationManifest" = ManifestSerDe.load_manifest_from_file(
                filename=filename, type=FoundationManifest
            )
            if name or codeartifact_domain or codeartifact_repository:
                msg_ctx.warn(
                    f'Reading parameters from {filename}, "name", "codeartifact-domain", '
                    'and "codeartifact-repository" ignored.'
                )
        elif name:
            if ssl_cert_arn:
                if not custom_domain_name:
                    raise ValueError('If "ssl_cert_arn" is provided, "custom_domain_name" should be provided')
            if custom_domain_name:
                if not ssl_cert_arn:
                    raise ValueError('If "custom_domain_name" is provided, "ssl_cert_arn" should be provided')

            manifest: FoundationManifest = FoundationManifest(  # type: ignore
                name=name,
                codeartifact_domain=codeartifact_domain,
                codeartifact_repository=codeartifact_repository,
                ssm_parameter_name=f"/orbit-f/{name}/manifest",
                networking=NetworkingManifest(
                    max_availability_zones=max_availability_zones,
                    frontend=FrontendNetworkingManifest(
                        ssl_cert_arn=ssl_cert_arn, custom_domain_name=custom_domain_name
                    ),
                    data=DataNetworkingManifest(internet_accessible=internet_accessibility),
                ),
            )
        else:
            msg_ctx.error('One of "filename" or "name" is required')
            raise ValueError('One of "filename" or "name" is required')

        ManifestSerDe.dump_manifest_to_ssm(manifest=manifest)
        msg_ctx.info(f"Manifest loaded: {manifest.name}")
        msg_ctx.progress(3)

        context: FoundationContext = ContextSerDe.load_context_from_manifest(manifest=manifest)
        msg_ctx.info("Current Context loaded")
        msg_ctx.progress(4)

        _deploy_toolkit(
            context=cast(Context, context),
            top_level="orbit-f",
        )
        msg_ctx.info("Toolkit deployed")
        msg_ctx.progress(8)

        bundle_path = bundle.generate_bundle(command_name="deploy_foundation", context=cast(Context, context))
        msg_ctx.progress(10)
        buildspec = codebuild.generate_spec(
            context=cast(Context, context),
            plugins=False,
            cmds_build=[f"orbit remote --command deploy_foundation {context.name}"],
        )
        msg_ctx.progress(11)
        remote.run(
            command_name="deploy_foundation",
            context=cast(Context, context),
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=90,
        )
        msg_ctx.info("Orbit Foundation deployed")
        msg_ctx.progress(100)


def deploy_env(
    filename: str,
    skip_images: bool,
    debug: bool,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        manifest: "Manifest" = ManifestSerDe.load_manifest_from_file(filename=filename, type=Manifest)
        msg_ctx.info(f"Manifest loaded: {filename}")
        msg_ctx.progress(3)

        manifest_validations(manifest)

        context: "Context" = ContextSerDe.load_context_from_manifest(manifest=manifest)
        image_manifests = {"code_build": manifest.images.code_build}

        for name in context.images.names:
            # We don't allow these images to be managed with an input Manifest
            # These images should be changed/maintained in manifests.py
            if name not in ["code_build", "k8s-utilities"]:
                image_manifests[name] = getattr(context.images, name) if skip_images else getattr(manifest.images, name)
        context.images = ImagesManifest(**image_manifests)  # type: ignore

        msg_ctx.info("Current Context loaded")
        msg_ctx.progress(4)

        _logger.debug("Inspecting possible manifest changes...")
        changeset: "Changeset" = extract_changeset(manifest=manifest, context=context, msg_ctx=msg_ctx)
        _logger.debug(f"Changeset:\n{dump_changeset_to_str(changeset=changeset)}")
        msg_ctx.progress(5)

        _deploy_toolkit(
            context=context,
        )
        msg_ctx.info("Toolkit deployed")
        msg_ctx.progress(10)

        bundle_path = bundle.generate_bundle(
            command_name="deploy",
            context=context,
            dirs=_get_images_dirs(context=context, manifest_filename=filename, skip_images=skip_images),
        )
        msg_ctx.progress(11)
        skip_images_remote_flag: str = "skip-images" if skip_images else "no-skip-images"
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=True,
            cmds_build=[f"orbit remote --command deploy_env {context.name} {skip_images_remote_flag}"],
            changeset=changeset,
        )
        remote.run(
            command_name="deploy",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=90,
        )
        msg_ctx.info("Orbit Workbench deployed")
        msg_ctx.progress(98)

        if cfn.does_stack_exist(stack_name=context.env_stack_name):
            context = ContextSerDe.load_context_from_manifest(manifest=manifest)
            msg_ctx.info(f"Context updated: {filename}")
        msg_ctx.progress(99)

        if context.cognito_users_url:
            msg_ctx.tip(f"Add users: {stylize(context.cognito_users_url, underline=True)}")
        else:
            RuntimeError("Cognito Users URL not found.")
        if context.landing_page_url:
            msg_ctx.tip(f"Access Orbit Workbench: {stylize(f'{context.landing_page_url}/orbit/login', underline=True)}")
        else:
            RuntimeError("Landing Page URL not found.")
        msg_ctx.progress(100)


def deploy_teams(
    filename: str,
    debug: bool,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        manifest: "Manifest" = ManifestSerDe.load_manifest_from_file(filename=filename, type=Manifest)
        msg_ctx.info(f"Manifest loaded: {filename}")
        msg_ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        msg_ctx.progress(3)

        context_parameter_name: str = f"/orbit/{manifest.name}/context"
        if not ssm.does_parameter_exist(name=context_parameter_name):
            msg_ctx.error(f"Orbit Environment {manifest.name} cannot be found in the current account and region.")
            return

        context: "Context" = ContextSerDe.load_context_from_manifest(manifest=manifest)
        msg_ctx.info("Current Context loaded")
        msg_ctx.info(f"Teams: {','.join([t.name for t in context.teams])}")
        msg_ctx.progress(4)

        _logger.debug("Inspecting possible manifest changes...")
        changeset: "Changeset" = extract_changeset(manifest=manifest, context=context, msg_ctx=msg_ctx)
        _logger.debug(f"Changeset:\n{dump_changeset_to_str(changeset=changeset)}")
        msg_ctx.progress(5)

        msg_ctx.progress(7)
        _logger.debug("Preparing bundle directory")
        dirs: List[Tuple[str, str]] = []
        dirs += _get_config_dirs(context=context, manifest_filename=filename)
        _logger.debug(f"*Directory={dirs}")
        dirs += _get_images_dirs(context=context, manifest_filename=filename, skip_images=True)
        _logger.debug(f"**Directory={dirs}")

        bundle_path = bundle.generate_bundle(
            command_name="deploy",
            context=context,
            dirs=dirs,
        )
        msg_ctx.progress(11)
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=True,
            cmds_build=[f"orbit remote --command deploy_teams {context.name}"],
            changeset=changeset,
        )
        remote.run(
            command_name="deploy",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=90,
        )
        msg_ctx.info("Orbit Workbench deployed")
        msg_ctx.progress(98)

        if cfn.does_stack_exist(stack_name=context.env_stack_name):
            context = ContextSerDe.load_context_from_ssm(env_name=manifest.name, type=Context)
            msg_ctx.info(f"Context updated: {filename}")
        msg_ctx.progress(99)

        if context.user_pool_id:
            cognito_users_url = orbit_cognito.get_users_url(user_pool_id=context.user_pool_id, region=context.region)
            msg_ctx.tip(f"Add users: {stylize(cognito_users_url, underline=True)}")

        if context.landing_page_url:
            msg_ctx.tip(f"Access Orbit Workbench: {stylize(f'{context.landing_page_url}/orbit/login', underline=True)}")
        else:
            raise RuntimeError("Landing Page URL not found.")
        msg_ctx.progress(100)


def _deploy_image(
    env: str,
    dir: str,
    name: str,
    script: Optional[str],
    build_args: Optional[List[str]],
    region: Optional[str],
    debug: bool,
) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as msg_ctx:
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)

        if cfn.does_stack_exist(stack_name=f"orbit-{context.name}") is False:
            msg_ctx.error("Please, deploy your environment before deploy any additional docker image")
            return

        msg_ctx.progress(3)

        bundle_path = bundle.generate_bundle(command_name=f"deploy_image-{name}", context=context, dirs=[(dir, name)])
        msg_ctx.progress(4)
        script_str = "NO_SCRIPT" if script is None else script
        build_args = [] if build_args is None else build_args
        buildspec = codebuild.generate_spec(
            context=context,
            plugins=True,
            cmds_build=[f"orbit remote --command _deploy_image {env} {name} {dir} {script_str} {' '.join(build_args)}"],
            changeset=None,
        )
        remote.run(
            command_name=f"deploy_image-{name}",
            context=context,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=msg_ctx.progress_bar_callback,
            timeout=30,
        )
        msg_ctx.info("Docker Image deploy into ECR")
        address = f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}-{name}"
        msg_ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        msg_ctx.progress(100)
