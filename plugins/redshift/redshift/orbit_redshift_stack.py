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
from typing import Any, Dict

from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda
from aws_cdk import aws_redshift as redshift
from aws_cdk import aws_secretsmanager, core
from aws_cdk.core import Construct, Environment, Stack, Tags

# if TYPE_CHECKING:
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.plugins.helpers import cdk_handler

# from aws_orbit.manifest.team import MANIFEST_TEAM_TYPE


_logger: logging.Logger = logging.getLogger(__name__)


def _lambda_path(path: str) -> str:
    PLUGIN_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
    LAMBDA_DIR = os.path.abspath(os.path.join(PLUGIN_ROOT_PATH, "./lambda_sources/"))
    return os.path.join(LAMBDA_DIR, path)


# def read_raw_manifest_ssm(manifest: "Manifest", team_name: str) -> Optional[MANIFEST_TEAM_TYPE]:
#     parameter_name: str = f"/orbit/{manifest.name}/teams/{team_name}/manifest"
#     _logger.debug("Trying to read manifest from SSM parameter (%s).", parameter_name)
#     client = manifest.boto3_client(service_name="ssm")
#     try:
#         json_str: str = client.get_parameter(Name=parameter_name)["Parameter"]["Value"]
#     except client.exceptions.ParameterNotFound:
#         _logger.debug("Team %s Manifest SSM parameter not found: %s", team_name, parameter_name)
#         return None
#     _logger.debug("Team %s Manifest SSM parameter found.", team_name)
#     return cast(MANIFEST_TEAM_TYPE, json.loads(json_str))


class RedshiftClusters(core.Construct):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        kms_key: kms.Key,
        team_space_props: Dict[str, Any],
        plugin_params: Dict[str, Any],
    ):
        super().__init__(scope, id)

        redshift_common = RedshiftClustersCommon(self, "redshift-common", kms_key, team_space_props, plugin_params)

        RedshiftFunctionStandard(self, "redshift-standard", redshift_common, kms_key)


class RedshiftClustersCommon(core.Construct):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        kms_key: kms.Key,
        team_space_props: Dict[str, Any],
        plugin_params: Dict[str, Any],
    ):
        super().__init__(scope, id)

        self.region = team_space_props["region"]
        self.account = team_space_props["account_id"]
        self.partition = team_space_props["partition"]
        self.env_name = team_space_props["env_name"]
        self.teamspace_name = team_space_props["teamspace_name"]
        self.lake_role_name = team_space_props["lake_role_name"]
        self.lake_role_arn = f"arn:{self.partition}:iam::{self.account}:role/{self.lake_role_name}"

        vpc_id: str = team_space_props["vpc_id"]
        vpc: ec2.Vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=vpc_id)

        # Adding plugin parameters to redshift parameter group
        self._parameter_group = redshift.CfnClusterParameterGroup(
            self,
            "parametergroup",
            description=f"Cluster parameter group for {self.env_name}-{self.teamspace_name}",
            parameter_group_family="redshift-1.0",
            parameters=[
                redshift.CfnClusterParameterGroup.ParameterProperty(
                    parameter_name="enable_user_activity_logging",
                    parameter_value=plugin_params.get("enable_user_activity_logging", "true"),
                ),
                redshift.CfnClusterParameterGroup.ParameterProperty(
                    parameter_name="require_ssl", parameter_value=plugin_params.get("require_ssl", "true")
                ),
                redshift.CfnClusterParameterGroup.ParameterProperty(
                    parameter_name="use_fips_ssl", parameter_value=plugin_params.get("use_fips_ssl", "true")
                ),
            ],
        )
        self._subnet_group = redshift.CfnClusterSubnetGroup(
            self,
            "subnetgroup",
            description=f"Cluster subnet group for {self.env_name}-{self.teamspace_name}",
            # subnet_ids=[subnet.subnet_id for subnet in vpc.private_subnets]
            subnet_ids=team_space_props["subnet_ids"],
        )
        # TODO - Check if required
        # smSecurityGroup = datamaker_team_space_props.sagemaker_security_group

        self._security_group = ec2.SecurityGroup(
            self,
            "orbit-redshift-sg",
            vpc=vpc,
            allow_all_outbound=False,
            description=f"OrbitTeamSpace Redshift Security Group for {self.env_name}-{self.teamspace_name}",
        )

        # TODO - Check if required
        # self._security_group.add_ingress_rule(
        #     smSecurityGroup,
        #     ec2.Port.tcp(5439)
        # )

        self._security_group.add_ingress_rule(self._security_group, ec2.Port.all_tcp())

        self._secret = aws_secretsmanager.Secret(
            self,
            "master-password",
            secret_name=f"orbit-redshift-master-{self.env_name}-{self.teamspace_name}",
            description="This secret has a dynamically generated master secret password for redshift cluster",
            generate_secret_string=aws_secretsmanager.SecretStringGenerator(
                secret_string_template='{ "username": "master"}',
                generate_string_key="password",
                password_length=62,
                exclude_characters='"@\\\/',  # noqa
                exclude_punctuation=True,
            ),
        )

        self._lambda_role: iam.Role = iam.Role(
            self,
            "lambda_orbit_lake_formation_trigger",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "lambda-policy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ec2:Describe*",
                                "ec2:CreateNetworkInterface",
                                "ec2:DeleteNetworkInterface",
                                "logs:Create*",
                                "logs:PutLogEvents",
                                "iam:CreateServiceLinkedRole",
                                "kms:TagResource",
                            ],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "redshift:*",
                            ],
                            resources=[
                                f"arn:{self.partition}:redshift:{self.region}:{self.account}:dbuser:{self.env_name}-{self.teamspace_name}*/master",  # noqa
                                f"arn:{self.partition}:redshift:{self.region}:{self.account}:dbname:{self.env_name}-{self.teamspace_name}*/defaultdb",  # noqa
                                f"arn:{self.partition}:redshift:{self.region}:{self.account}:cluster:{self.env_name}-{self.teamspace_name}*",  # noqa
                            ],
                        ),
                        iam.PolicyStatement(effect=iam.Effect.ALLOW, actions=["kms:*"], resources=[kms_key.key_arn]),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "iam:PassRole",
                            ],
                            resources=[self.lake_role_arn],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "secretsmanager:GetSecretValue",
                                "secretsmanager:DescribeSecret",
                                "secretsmanager:ListSecretVersionIds",
                            ],
                            resources=[self._secret.secret_arn],
                        ),
                    ]
                )
            },
        )


class RedshiftFunctionStandard(core.Construct):
    def __init__(self, scope: core.Construct, id: str, redshift_common: RedshiftClustersCommon, kms_key: kms.Key):
        super().__init__(scope, id)
        env_name: str = redshift_common.env_name
        teamspace_name: str = redshift_common.teamspace_name
        code = aws_lambda.Code.asset(_lambda_path(path="redshift_db_creator"))
        lake_role: iam.Role = iam.Role.from_role_arn(
            self,
            f"{env_name}-{teamspace_name}-role",
            redshift_common.lake_role_arn,
            mutable=False,
        )
        launch_name = "Standard"

        standard_function = aws_lambda.Function(
            self,
            f"orbit-{env_name}-{teamspace_name}-StartRedshift-Standard",
            function_name=f"orbit-{env_name}-{teamspace_name}-StartRedshift-{launch_name}",
            code=code,
            handler="redshift_functions.lambda_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            timeout=core.Duration.minutes(13),
            role=redshift_common._lambda_role,
            environment={
                "ClusterType": "multi-node",
                "NodeType": "DC2.large",
                "Nodes": "2",
                "Database": "defaultdb",
                "RedshiftClusterParameterGroup": redshift_common._parameter_group.ref,
                "RedshiftClusterSubnetGroup": redshift_common._subnet_group.ref,
                "RedshiftClusterSecurityGroup": redshift_common._security_group.security_group_id,
                "PortNumber": "5439",
                "SecretId": redshift_common._secret.secret_arn,
                "Role": redshift_common.lake_role_arn,
                "kms_key": kms_key.key_id,
                "Env": env_name,
                "TeamSpace": teamspace_name,
            },
        )
        standard_function.grant_invoke(lake_role)


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
            f"{team_manifest.manifest.name}-{team_manifest.name}-admn-role",
            f"arn:{core.Aws.PARTITION}:iam::{team_manifest.manifest.account_id}:role/orbit-{team_manifest.manifest.name}-admin",  # noqa
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
            "subnet_ids": [sm.subnet_id for sm in manifest.vpc.subnets]
        }

        # for sm in manifest.vpc.asdict()["subnets"]:
        #     print(sm["subnet-id"])

        # for sm in manifest.vpc.subnets:
        #     print(sm.subnet_id)

        self._redshift_clusters = RedshiftClusters(
            self,
            id="redshift-clusters-for-teamspace",
            kms_key=kms_key,
            team_space_props=team_space_props,
            plugin_params=parameters,
        )


if __name__ == "__main__":
    cdk_handler(stack_class=RedshiftStack)
