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

from datamaker_cli.cfn import deploy_template, destroy_stack
from datamaker_cli.demo import stack
from datamaker_cli.manifest import Manifest, SubnetKind, SubnetManifest
from datamaker_cli.spinner import start_spinner
from datamaker_cli.utils import does_cfn_exist

_logger: logging.Logger = logging.getLogger(__name__)


def _refresh_manifest(manifest: Manifest, stack_name: str) -> None:
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


def deploy(manifest: Manifest, filename: str) -> Manifest:
    if manifest.demo:
        stack_name: str = f"datamaker-demo-{manifest.name}"
        _logger.debug("Demo stack name: %s", stack_name)

        with start_spinner(msg=f"Synthetizing the DEMO CloudFormation stack: {stack_name}") as spinner:
            cfn_template_filename: str = stack.synth(stack_name=stack_name, filename=filename, env_name=manifest.name)
            _logger.debug("cfn_template_filename: %s", cfn_template_filename)
            spinner.succeed()

        with start_spinner(msg=f"Deploying the DEMO CloudFormation stack: {stack_name}") as spinner:
            deploy_template(stack_name=stack_name, filename=cfn_template_filename, env_tag=manifest.name)
            spinner.succeed()

        with start_spinner(msg=f"Refresing manifest file ({filename}) with the DEMO stack attributes") as spinner:
            _refresh_manifest(manifest=manifest, stack_name=stack_name)
            manifest.write_file(filename=filename)
            spinner.succeed()

    return manifest


def destroy(manifest: Manifest) -> Manifest:
    if manifest.demo:
        stack_name: str = f"datamaker-demo-{manifest.name}"
        if does_cfn_exist(stack_name=stack_name):
            with start_spinner(msg=f"Destroying the DEMO CloudFormation stack: {stack_name}") as spinner:
                destroy_stack(stack_name=stack_name)
                spinner.succeed()
    return manifest
