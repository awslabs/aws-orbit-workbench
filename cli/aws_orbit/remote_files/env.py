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
from typing import TYPE_CHECKING, List, Optional

from aws_orbit import ORBIT_CLI_ROOT, cdk, docker
from aws_orbit.services import cfn, ecr, iam, ssm

if TYPE_CHECKING:
    from aws_orbit.models.changeset import ListChangeset
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def deploy(
    context: "Context",
    eks_system_masters_roles_changes: Optional["ListChangeset"],
) -> None:
    _logger.debug("Stack name: %s", context.env_stack_name)

    if eks_system_masters_roles_changes and (
        eks_system_masters_roles_changes.added_values or eks_system_masters_roles_changes.removed_values
    ):
        iam.update_assume_role_roles(
            account_id=context.account_id,
            role_name=f"orbit-{context.name}-admin",
            roles_to_add=eks_system_masters_roles_changes.added_values,
            roles_to_remove=eks_system_masters_roles_changes.removed_values,
        )

    args: List[str] = [context.name]

    cdk.deploy(
        context=context,
        stack_name=context.env_stack_name,
        app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "env.py"),
        args=args,
    )
    context.fetch_env_data()


def destroy(context: "Context") -> None:
    _logger.debug("Stack name: %s", context.env_stack_name)
    if cfn.does_stack_exist(stack_name=context.env_stack_name):
        docker.login(context=context)
        _logger.debug("DockerHub and ECR Logged in")
        ecr.cleanup_remaining_repos(env_name=context.name)
        args = [context.name]
        cdk.destroy(
            context=context,
            stack_name=context.env_stack_name,
            app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "env.py"),
            args=args,
        )
        ssm.cleanup_context(env_name=context.name)
