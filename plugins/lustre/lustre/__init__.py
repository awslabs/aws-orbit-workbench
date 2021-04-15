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
from typing import TYPE_CHECKING, Any, Dict, Optional
import boto3
import botocore
from aws_orbit import sh, utils
from aws_orbit.plugins import hooks

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext
_logger: logging.Logger = logging.getLogger("aws_orbit")
POD_FILENAME = os.path.join(os.path.dirname(__file__), "lustre.yaml")


@hooks.deploy
def deploy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    vars: Dict[str, Optional[str]] = dict(
        team=team_context.name,
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        plugin_id=plugin_id,
        deploymentType='SCRATCH_2',
        sg=team_context.team_security_group_id,
        subnet=context.networking.data.nodes_subnets[0],
        s3importpath=f's3://{team_context.scratch_bucket}/{team_context.name}/lustre',
        s3exportpath=f's3://{team_context.scratch_bucket}/{team_context.name}/lustre'
    )

    input = POD_FILENAME
    output = os.path.join(os.path.dirname(POD_FILENAME), f"{plugin_id}-team.yaml")

    with open(input, "r") as file:
        content: str = file.read()

    content = utils.resolve_parameters(content, vars)

    _logger.debug("Kubectl Team %s context:\n%s", team_context.name, content)
    with open(output, "w") as file:
        file.write(content)

    ec2 = boto3.client("ec2")
    try:
        ec2.authorize_security_group_ingress(
            CidrIp='192.168.0.0/16',
            FromPort=988,
            ToPort=988,
            GroupId=team_context.team_security_group_id,
            IpProtocol='tcp',
        )
    except botocore.exceptions.ClientError as ex:
        if ex.response.get("Error", {}).get("Code", "Unknown") != "InvalidPermission.Duplicate":
            _logger.error("Error Authorizing Ingress", ex)
            raise
        else:
            _logger.debug("Ingress previously authorized")
    # run the POD to execute the script
    cmd = f"kubectl apply -f {output}  --namespace {team_context.name}"
    _logger.debug(cmd)
    sh.run(cmd)


@hooks.destroy
def destroy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Delete Plugin %s of Team Env name: %s | Team name: %s", plugin_id, context.name, team_context.name)

