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

from datamaker_cli.manifest import Manifest
from datamaker_cli.remote_files import cdk
from datamaker_cli.services.cloudformation import deploy_template, destroy_stack
from datamaker_cli.utils import does_cfn_exist

STACK_NAME = "datamaker-{env_name}"

_logger: logging.Logger = logging.getLogger(__name__)


def deploy(manifest: Manifest, filename: str) -> None:
    stack_name = STACK_NAME.format(env_name=manifest.name)
    _logger.debug("Stack name: %s", stack_name)
    if not does_cfn_exist(stack_name=stack_name) or manifest.dev:
        manifest.read_ssm()
        template_filename = cdk.env.synth(
            stack_name=stack_name, filename=filename, manifest=manifest, add_images=[], remove_images=[]
        )
        _logger.debug("template_filename: %s", template_filename)
        deploy_template(stack_name=stack_name, filename=template_filename, env_tag=f"datamaker-{manifest.name}")


def destroy(manifest: Manifest) -> None:
    stack_name = STACK_NAME.format(env_name=manifest.name)
    _logger.debug("Stack name: %s", stack_name)
    if manifest.demo and does_cfn_exist(stack_name=stack_name):
        destroy_stack(stack_name=stack_name)
