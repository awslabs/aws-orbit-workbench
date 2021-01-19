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

from typing import TYPE_CHECKING, Any, Dict, Optional, cast

import aws_cdk.aws_iam as iam
import aws_cdk.aws_kms as kms
import aws_cdk.core as core
from aws_cdk.core import Construct, Environment, Stack, Tags
from aws_orbit.plugins.helpers import cdk_handler

if TYPE_CHECKING:
    from aws_orbit.manifest import Manifest
    from aws_orbit.manifest.team import MANIFEST_TEAM_TYPE, TeamManifest

import json
import logging

from .orbit_redshift_constructs import RedshiftClusters

_logger: logging.Logger = logging.getLogger(__name__)


def read_raw_manifest_ssm(manifest: "Manifest", team_name: str) -> Optional[MANIFEST_TEAM_TYPE]:
    parameter_name: str = f"/orbit/{manifest.name}/teams/{team_name}/manifest"
    _logger.debug("Trying to read manifest from SSM parameter (%s).", parameter_name)
    client = manifest.boto3_client(service_name="ssm")
    try:
        json_str: str = client.get_parameter(Name=parameter_name)["Parameter"]["Value"]
    except client.exceptions.ParameterNotFound:
        _logger.debug("Team %s Manifest SSM parameter not found: %s", team_name, parameter_name)
        return None
    _logger.debug("Team %s Manifest SSM parameter found.", team_name)
    return cast(MANIFEST_TEAM_TYPE, json.loads(json_str))


class RedshiftStack(Stack):
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

        # team_ssm_response_dict = read_raw_manifest_ssm(manifest=team_manifest.manifest, team_name=team_manifest.name)
        admin_role = iam.Role.from_role_arn(
            self,
            f"{team_manifest.manifest.name}-{team_manifest.name}-role",
            f"orbit-{team_manifest.manifest.name}-admin",
            mutable=False,
        )

        kms_key: kms.Key = kms.Key(
            self,
            "team-kms-key",
            description=f"Key for TeamSpace {team_manifest.manifest.name}.{team_manifest.name}",
            trust_account_identities=True,
            removal_policy=core.RemovalPolicy.DESTROY,
            enable_key_rotation=True,
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        principals=[admin_role],
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "kms:Create*",
                            "kms:Describe*",
                            "kms:Enable*",
                            "kms:List*",
                            "kms:Put*",
                            "kms:Update*",
                            "kms:Revoke*",
                            "kms:Disable*",
                            "kms:Get*",
                            "kms:Delete*",
                            "kms:ScheduleKeyDeletion",
                            "kms:CancelKeyDeletion",
                        ],
                        resources=["*"],
                    )
                ]
            ),
        )
        # Collecting required parameters
        team_space_props: Dict[str, Any] = {
            "account_id": team_manifest.manifest.account_id,
            "region": team_manifest.manifest.region,
            "partition": core.Aws.PARTITION,
            "env_name": team_manifest.manifest.name,
            "teamspace_name": team_manifest.name,
            "lake_role_name": f"orbit-{team_manifest.manifest.name}-{team_manifest.name}-role",
            "vpc_id": manifest.vpc.asdict()["vpc-id"],
            "subnet_ids": [],
        }

        # for sm in manifest.vpc.asdict()["subnets"]:
        #     print(sm["subnet-id"])

        for sm in manifest.vpc.subnets:
            print(sm.subnet_id)

        self._redshift_clusters = RedshiftClusters(
            self,
            id="redshift-clusters-for-teamspace",
            kms_key=kms_key,
            team_space_props=team_space_props,
            plugin_params=parameters,
        )


if __name__ == "__main__":
    cdk_handler(stack_class=RedshiftStack)
