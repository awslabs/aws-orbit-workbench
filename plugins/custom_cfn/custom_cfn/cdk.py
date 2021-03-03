# type: ignore

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
from typing import TYPE_CHECKING, Any, Dict, cast

import yaml
from aws_cdk.core import CfnInclude, Construct, Environment, IConstruct, NestedStack, Stack, Tags
from aws_orbit.plugins.helpers import cdk_handler

from .yaml_loader import CfnYamlLoader

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger(__name__)


class Team(Stack):
    def __init__(
        self, scope: Construct, id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]
    ) -> None:
        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=context.account_id, region=context.region),
        )
        Tags.of(scope=cast(IConstruct, self)).add(key="Env", value=f"orbit-{context.name}")

        _logger.debug("Passing Plugin CDK Stack parameters to the Nested stack Cfn parameters")
        NestedCfnStack(self, id="custom-cfn-stack", parameters=parameters)


class NestedCfnStack(NestedStack):
    def __init__(self, scope: Construct, id: str, parameters: Dict[str, Any]) -> None:
        super().__init__(scope=scope, id=id)
        template_path = parameters["cfn_template_path"]
        _logger.debug(f"cfn_template_path={template_path}")
        if not os.path.isfile(template_path):
            raise FileNotFoundError(f"CloudFormation template not found at {template_path}")

        custom_cfn_yaml = yaml.load(open(template_path).read(), Loader=CfnYamlLoader)
        _logger.debug("Yaml loading compelted")
        CfnInclude(self, id="custom-cfn-nested-stack", template=custom_cfn_yaml)
        _logger.debug("Nested stack addition completed")


if __name__ == "__main__":
    cdk_handler(stack_class=Team)
