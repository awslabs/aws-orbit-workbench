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
import uuid
from typing import Dict, List, Optional, Tuple, cast

import click

from datamaker_cli import bundle, dockerhub, plugins, remote, toolkit
from datamaker_cli.manifest import Manifest, SubnetKind, SubnetManifest, read_manifest_file
from datamaker_cli.messages import MessagesContext, stylize
from datamaker_cli.services import cfn, codebuild

_logger: logging.Logger = logging.getLogger(__name__)


def _request_dockerhub_credential(ctx: MessagesContext) -> Tuple[str, str]:
    if ctx.pbar is not None:
        ctx.pbar.clear()
    username = cast(str, click.prompt("Please enter the DockerHub username", type=str, hide_input=False))
    password = cast(str, click.prompt("Please enter the DockerHub password", type=str, hide_input=True))
    return username, password


def refresh_manifest_file_with_demo_attrs(manifest: Manifest) -> None:
    stack_name = f"datamaker-{manifest.name}-demo"
    resp_type = Dict[str, List[Dict[str, List[Dict[str, str]]]]]
    response: resp_type = manifest.get_boto3_client("cloudformation").describe_stacks(StackName=stack_name)
    if len(response["Stacks"]) < 1:
        raise RuntimeError(f"Cloudformation {stack_name} stack not found. Please deploy it.")
    subnets: List[SubnetManifest] = []
    for output in response["Stacks"][0]["Outputs"]:
        if output["ExportName"] == f"datamaker-{manifest.name}-private-subnets-ids":
            for subnet_id in output["OutputValue"].split(","):
                subnets.append(SubnetManifest(subnet_id=subnet_id, kind=SubnetKind.private))
        elif output["ExportName"] == f"datamaker-{manifest.name}-public-subnets-ids":
            for subnet_id in output["OutputValue"].split(","):
                subnets.append(SubnetManifest(subnet_id=subnet_id, kind=SubnetKind.public))
    manifest.vpc.subnets = subnets
    manifest.write_file(filename=manifest.filename)


def deploy_toolkit(
    filename: str, manifest: Manifest, username: Optional[str], password: Optional[str], ctx: MessagesContext
) -> None:
    stack_name: str = f"datamaker-{manifest.name}-toolkit"
    credential_received: bool = username is not None and password is not None
    stack_exist: bool = cfn.does_stack_exist(manifest=manifest, stack_name=stack_name)
    if stack_exist:
        credential_exist: bool = dockerhub.does_credential_exist(manifest=manifest)
    else:
        credential_exist = False

    if stack_exist:
        if not credential_exist and not credential_received:
            username, password = _request_dockerhub_credential(ctx=ctx)
            dockerhub.store_credential(manifest=manifest, username=username, password=password)
            credential_exist = True
        elif credential_received:
            dockerhub.store_credential(manifest=manifest, username=cast(str, username), password=cast(str, password))
            credential_exist = True
    else:
        manifest.deploy_id = uuid.uuid4().hex[:6]
        if not credential_received:
            username, password = _request_dockerhub_credential(ctx=ctx)
            credential_exist = False

    ctx.progress(5)
    _logger.debug("manifest.deploy_id: %s", manifest.deploy_id)
    if stack_exist is False or manifest.dev:
        template_filename = toolkit.synth(filename=filename, manifest=manifest)
        cfn.deploy_template(
            manifest=manifest, stack_name=stack_name, filename=template_filename, env_tag=f"datamaker-{manifest.name}"
        )

    if credential_exist is False:
        dockerhub.store_credential(manifest=manifest, username=cast(str, username), password=cast(str, password))


def deploy_image(filename: str, dir: str, name: str, script: Optional[str], debug: bool) -> None:
    with MessagesContext("Deploying Docker Image", debug=debug) as ctx:
        manifest = read_manifest_file(filename=filename)
        ctx.info(f"Manifest loaded: {filename}")
        if cfn.does_stack_exist(manifest=manifest, stack_name=f"datamaker-{manifest.name}") is False:
            ctx.error("Please, deploy your environment before deploy any addicional docker image")
            return
        bundle_path = bundle.generate_bundle(command_name=f"deploy_image-{name}", manifest=manifest, dirs=[(dir, name)])
        ctx.progress(3)
        script_str = "" if script is None else script
        buildspec = codebuild.generate_spec(
            manifest=manifest,
            plugins=False,
            cmds_build=[f"datamaker remote --command deploy_image cdk=true {name} {script_str}"],
        )
        remote.run(
            command_name=f"deploy_image-{name}",
            manifest=manifest,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=ctx.progress_bar_callback,
            timeout=10,
        )
        ctx.info("Docker Image deploy into ECR")
        ctx.progress(100)


def deploy(filename: str, debug: bool, username: Optional[str] = None, password: Optional[str] = None) -> None:
    with MessagesContext("Deploying", debug=debug) as ctx:
        manifest = read_manifest_file(filename=filename)
        ctx.info(f"Manifest loaded: {filename}")
        ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        ctx.progress(2)

        plugins.load_plugins(manifest=manifest)
        ctx.info(f"Plugins: {','.join([p.name for p in manifest.plugins])}")
        ctx.progress(3)

        deploy_toolkit(filename=filename, manifest=manifest, username=username, password=password, ctx=ctx)
        ctx.info("Toolkit deployed")
        ctx.progress(10)

        if manifest.dev:
            dirs = [
                (os.path.join(manifest.filename_dir, "images", name), name)
                for name in ("landing-page", "jupyter-hub", "jupyter-user")
            ]
        else:
            dirs = []
        bundle_path = bundle.generate_bundle(command_name="deploy", manifest=manifest, dirs=dirs)
        ctx.progress(15)
        buildspec = codebuild.generate_spec(
            manifest=manifest,
            plugins=True,
            cmds_build=["datamaker remote --command deploy"],
        )
        remote.run(
            command_name="deploy",
            manifest=manifest,
            bundle_path=bundle_path,
            buildspec=buildspec,
            codebuild_log_callback=ctx.progress_bar_callback,
            timeout=45,
        )
        ctx.info("DataMaker deployed")
        ctx.progress(98)

        if manifest.demo and cfn.does_stack_exist(manifest=manifest, stack_name=f"datamaker-{manifest.name}-demo"):
            refresh_manifest_file_with_demo_attrs(manifest=manifest)
            ctx.info(f"Manifest updated: {filename}")
        ctx.progress(99)

        manifest.read_ssm()
        if manifest.cognito_users_urls:
            ctx.tip(f"Add users: {stylize(manifest.cognito_users_urls, underline=True)}")
        else:
            RuntimeError("Cognito Users URL not found.")
        if manifest.landing_page_url:
            ctx.tip(f"Access DataMaker: {stylize(manifest.landing_page_url, underline=True)}")
        else:
            RuntimeError("Landing Page URL not found.")
        ctx.progress(100)
