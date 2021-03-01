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
from typing import TypeVar

from aws_orbit import cdk
from aws_orbit.models.context import Context, FoundationContext
from aws_orbit.services import cfn, s3

_logger: logging.Logger = logging.getLogger(__name__)


T = TypeVar("T")


def deploy(context: T) -> None:
    if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
        raise ValueError("Unknown 'context' Type")
    _logger.debug("Deploying %s CDK Toolkit...", context.cdk_toolkit.stack_name)
    cdk.deploy_toolkit(context=context)


def destroy(context: T) -> None:
    if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
        raise ValueError("Unknown 'context' Type")
    _logger.debug("Destroying %s CDK Toolkit...", context.cdk_toolkit.stack_name)
    if context.cdk_toolkit.s3_bucket:
        if cfn.does_stack_exist(stack_name=context.cdk_toolkit.stack_name):
            try:
                s3.delete_bucket(bucket=context.cdk_toolkit.s3_bucket)
            except Exception as ex:
                _logger.debug("Skipping Toolkit bucket deletion. Cause: %s", ex)
            cfn.destroy_stack(stack_name=context.cdk_toolkit.stack_name)
