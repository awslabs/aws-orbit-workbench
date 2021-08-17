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
from typing import cast

from aws_orbit import ORBIT_CLI_ROOT, cdk, cleanup
from aws_orbit.models.context import FoundationContext
from aws_orbit.remote_files.cert import check_cert
from aws_orbit.services import cfn, ssm, vpc

_logger: logging.Logger = logging.getLogger(__name__)


def _fetch_vpc_id(context: "FoundationContext") -> str:
    return cast(str, ssm.get_parameter(name=cast(str, context.resources_ssm_parameter_name))["VpcId"])


def deploy(context: "FoundationContext") -> None:
    stack_name: str = cast(str, context.stack_name)

    _logger.debug("Deploying self signed cert...")
    ssl_cert_arn = check_cert(context=context)

    _logger.debug("Deploying %s Foundation...", stack_name)
    cdk.deploy(
        context=context,
        stack_name=stack_name,
        app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "foundation.py"),
        args=[context.name, ssl_cert_arn],
    )
    _logger.debug("Enabling private dns for codeartifact vpc endpoints")
    vpc_id: str = _fetch_vpc_id(context=context)
    vpc.modify_vpc_endpoint(vpc_id=vpc_id, service_name="codeartifact.repositories", private_dns_enabled=True)
    vpc.modify_vpc_endpoint(vpc_id=vpc_id, service_name="codeartifact.api", private_dns_enabled=True)


def destroy(context: "FoundationContext") -> None:
    if cfn.does_stack_exist(stack_name=cast(str, context.stack_name)):
        cleanup.foundation_remaining_dependencies(context=context)
        cleanup.delete_cert_from_iam(context=context)
        _logger.debug("Destroying Foundation...")
        cdk.destroy(
            context=context,
            stack_name=cast(str, context.stack_name),
            app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "foundation.py"),
            args=[context.name],
        )
