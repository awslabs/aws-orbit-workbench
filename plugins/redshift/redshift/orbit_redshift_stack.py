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
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda
from aws_cdk import aws_redshift as redshift
from aws_cdk import aws_secretsmanager, core
from aws_cdk.core import Construct, Environment, IConstruct, Stack, Tags
from aws_orbit.plugins.helpers import cdk_handler

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger(__name__)


def _lambda_path(path: str) -> str:
    PLUGIN_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
    LAMBDA_DIR = os.path.abspath(os.path.join(PLUGIN_ROOT_PATH, "./lambda_sources/"))
    return os.path.join(LAMBDA_DIR, path)


class RedshiftClusters(core.Construct):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        team_space_props: Dict[str, Any],
        plugin_params: Dict[str, Any],
    ):
        super().__init__(scope, id)

        redshift_common = RedshiftClustersCommon(self, "redshift-common", team_space_props, plugin_params)

        RedshiftFunctionStandard(self, "redshift-standard", redshift_common, plugin_params)


class RedshiftClustersCommon(core.Construct):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
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
        self.team_security_group_id = team_space_props["team_security_group_id"]
        self.team_kms_key_arn = team_space_props["team_kms_key_arn"]

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
                    parameter_name="require_ssl",
                    parameter_value=plugin_params.get("require_ssl", "true"),
                ),
                redshift.CfnClusterParameterGroup.ParameterProperty(
                    parameter_name="use_fips_ssl",
                    parameter_value=plugin_params.get("use_fips_ssl", "true"),
                ),
            ],
        )
        self._subnet_group = redshift.CfnClusterSubnetGroup(
            self,
            "subnetgroup",
            description=f"Cluster subnet group for {self.env_name}-{self.teamspace_name}",
            subnet_ids=team_space_props["subnet_ids"],
        )

        self._team_security_group = ec2.SecurityGroup.from_security_group_id(
            self,
            id=f"{self.env_name}-{self.teamspace_name}-sg",
            security_group_id=self.team_security_group_id,
            mutable=False,
        )

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
            assumed_by=cast(iam.IPrincipal, iam.ServicePrincipal("lambda.amazonaws.com")),
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
                                f"arn:{self.partition}:redshift:{self.region}:{self.account}:dbuser:orbit-{self.env_name}-{self.teamspace_name}*/master",  # noqa
                                f"arn:{self.partition}:redshift:{self.region}:{self.account}:dbname:orbit-{self.env_name}-{self.teamspace_name}*/defaultdb",  # noqa
                                f"arn:{self.partition}:redshift:{self.region}:{self.account}:cluster:orbit-{self.env_name}-{self.teamspace_name}*",  # noqa
                            ],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["kms:*"],
                            resources=[self.team_kms_key_arn],
                        ),
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
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        redshift_common: RedshiftClustersCommon,
        plugin_params: Dict[str, Any],
    ):
        super().__init__(scope, id)
        env_name: str = redshift_common.env_name
        teamspace_name: str = redshift_common.teamspace_name
        code = aws_lambda.Code.asset(_lambda_path(path="redshift_db_creator"))
        region: str = redshift_common.region

        if redshift_common.lake_role_arn is None:
            raise ValueError("Orbit lake role arn required")

        lake_role = iam.Role.from_role_arn(
            self,
            f"{env_name}-{teamspace_name}-{region}-role",
            redshift_common.lake_role_arn,
            mutable=False,
        )
        launch_name = "Standard"
        kms_key_id = redshift_common.team_kms_key_arn.split("/")[-1]
        standard_function = aws_lambda.Function(
            self,
            f"orbit-{env_name}-{teamspace_name}-StartRedshift-Standard",
            function_name=f"orbit-{env_name}-{teamspace_name}-StartRedshift-{launch_name}",
            code=code,
            handler="redshift_functions.lambda_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            timeout=core.Duration.minutes(13),
            role=cast(Optional[iam.IRole], redshift_common._lambda_role),
            environment={
                "ClusterType": "multi-node",
                "NodeType": plugin_params.get("node_type", "DC2.large"),
                "Nodes": plugin_params.get("number_of_nodes", "2"),
                "Database": "defaultdb",
                "RedshiftClusterParameterGroup": redshift_common._parameter_group.ref,
                "RedshiftClusterSubnetGroup": redshift_common._subnet_group.ref,
                "RedshiftClusterSecurityGroup": redshift_common._team_security_group.security_group_id,
                "PortNumber": "5439",
                "SecretId": redshift_common._secret.secret_arn,
                "Role": redshift_common.lake_role_arn,
                "kms_key": kms_key_id,
                "Env": env_name,
                "TeamSpace": teamspace_name,
            },
        )
        standard_function.grant_invoke(lake_role)


class RedshiftStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        context: "Context",
        team_context: "TeamContext",
        parameters: Dict[str, Any],
    ) -> None:

        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=context.account_id, region=context.region),
        )
        Tags.of(scope=cast(IConstruct, self)).add(key="Env", value=f"orbit-{context.name}")

        # Collecting required parameters
        team_space_props: Dict[str, Any] = {
            "account_id": context.account_id,
            "region": context.region,
            "partition": core.Aws.PARTITION,
            "env_name": context.name,
            "teamspace_name": team_context.name,
            "lake_role_name": f"orbit-{context.name}-{team_context.name}-{context.region}-role",
            "vpc_id": context.networking.vpc_id,
            "subnet_ids": context.networking.data.nodes_subnets,
            "team_security_group_id": team_context.team_security_group_id,
            "team_kms_key_arn": team_context.team_kms_key_arn,
        }

        self._redshift_clusters = RedshiftClusters(
            self,
            id="redshift-clusters-for-teamspace",
            team_space_props=team_space_props,
            plugin_params=parameters,
        )


if __name__ == "__main__":
    cdk_handler(stack_class=RedshiftStack)
