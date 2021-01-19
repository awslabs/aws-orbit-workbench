import logging
from typing import Any, Dict

from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda
from aws_cdk import aws_redshift as redshift
from aws_cdk import aws_secretsmanager, core

from . import _lambda_path

logging.basicConfig(format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()


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

        vpc_id: str = team_space_props["vpc-id"]
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
