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

from datamaker_cli.cdk import env, team
from datamaker_cli.cfn import deploy_template, destroy_stack
from datamaker_cli.manifest import Manifest
from datamaker_cli.spinner import start_spinner
from datamaker_cli.utils import does_cfn_exist

_logger: logging.Logger = logging.getLogger(__name__)


def deploy(manifest: Manifest, filename: str) -> Manifest:
    manifest.read_ssm()

    stack_name: str = f"datamaker-{manifest.name}"
    with start_spinner(msg=f"Synthetizing the {manifest.name} environment CloudFormation stack") as spinner:
        cfn_template_filename = env.synth(stack_name=stack_name, filename=filename, manifest=manifest)
        spinner.succeed()
    with start_spinner(msg=f"Deploying the {manifest.name} environment CloudFormation stack") as spinner:
        deploy_template(stack_name=stack_name, filename=cfn_template_filename, env_tag=f"datamaker-{manifest.name}")
        spinner.succeed()
    manifest.read_ssm()

    for team_manifest in manifest.teams:
        stack_name = f"datamaker-{manifest.name}-{team_manifest.name}"
        with start_spinner(msg=f"Synthetizing the {team_manifest.name} team-space CloudFormation stack") as spinner:
            cfn_template_filename = team.synth(
                stack_name=stack_name, filename=filename, manifest=manifest, team_manifest=team_manifest
            )
            spinner.succeed()
        with start_spinner(msg=f"Deploying the {team_manifest.name} team-space CloudFormation stack") as spinner:
            deploy_template(stack_name=stack_name, filename=cfn_template_filename, env_tag=f"datamaker-{manifest.name}")
            spinner.succeed()
    manifest.read_ssm()

    return manifest


def destroy(manifest: Manifest) -> Manifest:

    for team_manifest in manifest.teams:
        stack_name: str = f"datamaker-{manifest.name}-{team_manifest.name}"
        with start_spinner(msg=f"Destroying the {team_manifest.name} team-space CDK stack") as spinner:
            if does_cfn_exist(stack_name=stack_name):
                destroy_stack(stack_name=stack_name)
            spinner.succeed()

    stack_name = f"datamaker-{manifest.name}"
    with start_spinner(msg=f"Destroying the {manifest.name} environment CDK stack") as spinner:
        if does_cfn_exist(stack_name=stack_name):
            destroy_stack(stack_name=stack_name)
        spinner.succeed()

    return manifest
