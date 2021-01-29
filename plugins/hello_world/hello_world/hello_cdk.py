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
from typing import Any, Dict

import aws_cdk.aws_ssm as ssm
from aws_cdk.core import Construct, Environment, Stack, Tags
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.plugins.helpers import cdk_handler

_logger: logging.Logger = logging.getLogger("aws_orbit")


class MyStack(Stack):
    def __init__(
        self, scope: Construct, id: str, manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]
    ) -> None:

        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=manifest.account_id, region=manifest.region),
        )
        Tags.of(scope=self).add(key="Env", value=f"orbit-{manifest.name}")
        _logger.info(f"Plugin parameters: {parameters}")
        # just showing how to create resource.  Do not forget to update the IAM policy or make sure the attached policy
        # for the team is allowing the creation and destruction of the resource.
        ssm_parameter: str = f"/orbit/{team_manifest.manifest.name}/{team_manifest.name}/hello-plugin"
        ssm.StringParameter(
            scope=self, id="param", string_value="testing plugin hello world", parameter_name=ssm_parameter
        )


if __name__ == "__main__":
    cdk_handler(stack_class=MyStack)
