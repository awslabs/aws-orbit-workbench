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

from aws_orbit import cdk
from aws_orbit.manifest import Manifest
from aws_orbit.services import cfn, s3

_logger: logging.Logger = logging.getLogger(__name__)


def deploy(manifest: Manifest) -> None:
    _logger.debug("Deploying %s CDK Toolkit...", manifest.cdk_toolkit_stack_name)
    cdk.deploy_toolkit(manifest=manifest)


def destroy(manifest: Manifest) -> None:
    _logger.debug("Destroying %s CDK Toolkit...", manifest.cdk_toolkit_stack_name)
    if manifest.cdk_toolkit_stack_name and manifest.cdk_toolkit_s3_bucket:
        if cfn.does_stack_exist(manifest=manifest, stack_name=manifest.cdk_toolkit_stack_name):
            try:
                s3.delete_bucket(manifest=manifest, bucket=manifest.cdk_toolkit_s3_bucket)
            except Exception as ex:
                _logger.debug("Skipping Toolkit bucket deletion. Cause: %s", ex)
            cfn.destroy_stack(manifest=manifest, stack_name=manifest.cdk_toolkit_stack_name)
