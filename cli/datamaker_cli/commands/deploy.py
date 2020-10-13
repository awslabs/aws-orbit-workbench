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
from typing import Dict, List

import boto3

from datamaker_cli import plugins, toolkit
from datamaker_cli.manifest import Manifest, SubnetKind, SubnetManifest, read_manifest_file
from datamaker_cli.messages import MessagesContext
from datamaker_cli.remote import execute_remote
from datamaker_cli.services.cfn import deploy_template
from datamaker_cli.utils import does_cfn_exist

_logger: logging.Logger = logging.getLogger(__name__)


def refresh_manifest_file_with_demo_attrs(filename: str, manifest: Manifest) -> None:
    stack_name = f"datamaker-{manifest.name}-demo"
    resp_type = Dict[str, List[Dict[str, List[Dict[str, str]]]]]
    response: resp_type = boto3.client("cloudformation").describe_stacks(StackName=stack_name)
    if len(response["Stacks"]) < 1:
        raise RuntimeError(f"Cloudformation {stack_name} stack not found. Please deploy it.")
    subnets: List[SubnetManifest] = []
    for output in response["Stacks"][0]["Outputs"]:
        if output["ExportName"] == f"{stack_name}-private-subnets-ids":
            for subnet_id in output["OutputValue"].split(","):
                subnets.append(SubnetManifest(subnet_id=subnet_id, kind=SubnetKind.private))
        elif output["ExportName"] == f"{stack_name}-public-subnets-ids":
            for subnet_id in output["OutputValue"].split(","):
                subnets.append(SubnetManifest(subnet_id=subnet_id, kind=SubnetKind.public))
    manifest.vpc.subnets = subnets
    manifest.write_file(filename=filename)


def deploy_toolkit(filename: str, manifest: Manifest) -> None:
    stack_name = f"datamaker-{manifest.name}-toolkit"
    if not does_cfn_exist(stack_name=stack_name) or manifest.dev:
        template_filename = toolkit.synth(filename=filename, manifest=manifest)
        deploy_template(stack_name=stack_name, filename=template_filename, env_tag=f"datamaker-{manifest.name}")


def deploy(filename: str, debug: bool) -> None:
    with MessagesContext("Deploying", debug=debug) as ctx:
        manifest = read_manifest_file(filename=filename)
        ctx.info(f"Manifest loaded: {filename}")
        ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        ctx.progress(2)

        plugins.load_plugins(manifest=manifest)
        ctx.info(f"Plugins: {','.join([p.name for p in manifest.plugins])}")
        ctx.progress(3)

        deploy_toolkit(filename=filename, manifest=manifest)
        ctx.info("Toolkit deployed")
        ctx.progress(10)

        execute_remote(filename=filename, manifest=manifest, command="deploy", progress_callback=ctx.progress_callback)
        ctx.info("DataMaker deployed")
        ctx.progress(99)

        if manifest.demo and does_cfn_exist(stack_name=f"datamaker-{manifest.name}-demo"):
            refresh_manifest_file_with_demo_attrs(filename=filename, manifest=manifest)
            ctx.info(f"Manifest updated: {filename}")
        ctx.progress(100)
