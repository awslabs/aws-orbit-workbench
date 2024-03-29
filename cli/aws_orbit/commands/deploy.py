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
from typing import List, Optional, cast

from aws_orbit import toolkit
from aws_orbit.messages import MessagesContext, stylize
from aws_orbit.models.changeset import Changeset, dump_changeset_to_str, extract_changeset
from aws_orbit.models.context import Context, ContextSerDe, FoundationContext
from aws_orbit.models.manifest import (
    DataNetworkingManifest,
    FoundationManifest,
    FrontendNetworkingManifest,
    Manifest,
    ManifestSerDe,
    NetworkingManifest,
    manifest_validations,
)
from aws_orbit.remote_files import deploy
from aws_orbit.services import cfn
from aws_orbit.services import cognito as orbit_cognito
from aws_orbit.services import kms, ssm
from aws_orbit.utils import get_account_id, get_region

_logger: logging.Logger = logging.getLogger(__name__)


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

        msg_ctx.info("Encrypting credentials with Toolkit KMS Key")
        ciphertext = kms.encrypt(
            context=context, plaintext=json.dumps({registry: {"username": username, "password": password}})
        )
        msg_ctx.progress(20)

        msg_ctx.info("Starting Remote CodeBuild to deploy credentials")

        deploy.deploy_credentials(env_name=context.name, ciphertext=ciphertext)

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
    ssl_cert_arn: Optional[str] = None,
    custom_domain_name: Optional[str] = None,
    max_availability_zones: Optional[int] = None,
    role_prefix: Optional[str] = None,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        if filename:
            manifest: "FoundationManifest" = ManifestSerDe.load_manifest_from_file(
                filename=filename, type=FoundationManifest
            )
            if name:
                msg_ctx.warn(f'Reading parameters from {filename}, "name" ignored.')
        elif name:
            if ssl_cert_arn:
                if not custom_domain_name:
                    raise ValueError('If "ssl_cert_arn" is provided, "custom_domain_name" should be provided')
            if custom_domain_name:
                if not ssl_cert_arn:
                    raise ValueError('If "custom_domain_name" is provided, "ssl_cert_arn" should be provided')

            manifest: FoundationManifest = FoundationManifest(  # type: ignore
                name=name,
                ssm_parameter_name=f"/orbit-f/{name}/manifest",
                role_prefix=role_prefix,
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
        msg_ctx.progress(50)

        deploy.deploy_foundation(env_name=context.name)

        msg_ctx.info("Orbit Foundation deployed")
        msg_ctx.progress(100)


def deploy_env(
    filename: str,
    debug: bool,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        manifest: "Manifest" = ManifestSerDe.load_manifest_from_file(filename=filename, type=Manifest)
        msg_ctx.info(f"Manifest loaded: {filename}")
        msg_ctx.progress(5)

        manifest_dir: str = os.path.dirname(os.path.abspath(filename))
        _logger.debug("manifest directory is set to %s", manifest_dir)

        manifest_validations(manifest)

        context: "Context" = ContextSerDe.load_context_from_manifest(manifest=manifest)

        msg_ctx.info("Current Context loaded")
        msg_ctx.progress(10)

        _logger.debug("Inspecting possible manifest changes...")
        changeset: "Changeset" = extract_changeset(manifest=manifest, context=context, msg_ctx=msg_ctx)
        _logger.debug(f"Changeset:\n{dump_changeset_to_str(changeset=changeset)}")
        msg_ctx.progress(15)

        _deploy_toolkit(
            context=context,
        )
        msg_ctx.info("Toolkit deployed")
        msg_ctx.progress(30)

        deploy.deploy_env(
            env_name=context.name,
            manifest_dir=manifest_dir,
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
        msg_ctx.progress(5)

        manifest_dir: str = os.path.dirname(os.path.abspath(filename))
        _logger.debug("manifest directory is set to %s", manifest_dir)

        context_parameter_name: str = f"/orbit/{manifest.name}/context"
        if not ssm.does_parameter_exist(name=context_parameter_name):
            msg_ctx.error(f"Orbit Environment {manifest.name} cannot be found in the current account and region.")
            return

        context: "Context" = ContextSerDe.load_context_from_manifest(manifest=manifest)
        msg_ctx.info("Current Context loaded")
        msg_ctx.info(f"Teams: {','.join([t.name for t in context.teams])}")
        msg_ctx.progress(10)

        _logger.debug("Inspecting possible manifest changes...")
        changeset: "Changeset" = extract_changeset(manifest=manifest, context=context, msg_ctx=msg_ctx)
        _logger.debug(f"Changeset:\n{dump_changeset_to_str(changeset=changeset)}")

        msg_ctx.progress(30)

        deploy.deploy_teams(
            env_name=context.name,
            manifest_dir=manifest_dir,
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


def deploy_images(debug: bool, filename: str, reqested_image: Optional[str] = None) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        msg_ctx.progress(2)

        manifest: "Manifest" = ManifestSerDe.load_manifest_from_file(filename=filename, type=Manifest)
        msg_ctx.info(f"Manifest loaded: {filename}")
        msg_ctx.progress(3)

        context_parameter_name: str = f"/orbit/{manifest.name}/context"
        if not ssm.does_parameter_exist(name=context_parameter_name):
            msg_ctx.error(f"Orbit Environment {manifest.name} cannot be found in the current account and region.")
            return
        env = manifest.name
        msg_ctx.info(f"Deploying images for env {env}")
        deploy.deploy_images_remotely(env=env, requested_image=reqested_image)
        msg_ctx.progress(95)
        msg_ctx.progress(100)


def deploy_user_image(
    debug: bool,
    path: str,
    env: str,
    image_name: str,
    script: Optional[str],
    build_args: Optional[List[str]],
    timeout: int = 45,
) -> None:
    with MessagesContext("Deploying", debug=debug) as msg_ctx:
        context_parameter_name: str = f"/orbit/{env}/context"
        if not ssm.does_parameter_exist(name=context_parameter_name):
            msg_ctx.error(f"Orbit Environment {env} cannot be found in the current account and region.")
            return
        msg_ctx.progress(2)
        deploy.deploy_user_image(
            path=path, image_name=image_name, env=env, script=script, build_args=build_args, timeout=timeout
        )
        msg_ctx.progress(95)
        address = f"{get_account_id()}.dkr.ecr.{get_region()}.amazonaws.com/orbit-{env}/users/{image_name}"

        msg_ctx.info(f"ECR Image Address={address}")
        msg_ctx.tip(f"ECR Image Address: {stylize(address, underline=True)}")
        msg_ctx.progress(100)
