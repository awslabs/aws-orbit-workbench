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

import os
import shutil
from typing import List, cast

import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_efs as efs
import aws_cdk.aws_iam as iam
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_ssm as ssm
from aws_cdk.core import App, Construct, Duration, Environment, IConstruct, Stack, Tags

from datamaker_cli.manifest import Manifest, SubnetKind, TeamManifest
from datamaker_cli.utils import path_from_filename


class Team(Stack):
    def __init__(self, scope: Construct, id: str, manifest: Manifest, team_manifest: TeamManifest) -> None:
        self.scope = scope
        self.id = id
        self.manifest = manifest
        self.team_manifest = team_manifest
        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=self.manifest.account_id, region=self.manifest.region),
        )
        Tags.of(scope=self).add(key="Env", value=f"datamaker-{self.manifest.name}")
        self.i_vpc = ec2.Vpc.from_vpc_attributes(
            scope=self,
            id="vpc",
            vpc_id=self.manifest.vpc.vpc_id,
            availability_zones=self.manifest.vpc.availability_zones,
        )
        self.i_private_subnets = self._initialize_private_subnets()
        self.policy: str = str(self.team_manifest.policy)
        self.scratch_bucket: s3.Bucket = self._create_scratch_bucket()
        self.role_eks_nodegroup = self._create_role()
        self.sg_efs: ec2.SecurityGroup = self._create_sg_efs()
        self.efs: efs.FileSystem = self._create_efs()
        self.user_pool_group: cognito.CfnUserPoolGroup = self._create_user_pool_group()
        self.manifest_parameter = self._create_manifest_parameter()

    def _initialize_private_subnets(self) -> List[ec2.ISubnet]:
        return [
            ec2.PrivateSubnet.from_subnet_attributes(
                scope=self,
                id=s.subnet_id,
                subnet_id=s.subnet_id,
                availability_zone=s.availability_zone,
                route_table_id=s.route_table_id,
            )
            for s in self.manifest.vpc.subnets
            if s.kind == SubnetKind.private
        ]

    def _create_role(self) -> iam.Role:
        env_name = self.manifest.name
        team_name = self.team_manifest.name
        partition = self.partition
        region = self.region

        lake_role_name: str = f"datamaker-{env_name}-{team_name}-role"
        code_artifact_user_policy = iam.ManagedPolicy(
            scope=self,
            id="code_artifact_user",
            managed_policy_name=f"datamaker-{env_name}-{team_name}-ca-access",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "codeartifact:DescribePackageVersion",
                        "codeartifact:DescribeRepository",
                        "codeartifact:GetPackageVersionReadme",
                        "codeartifact:GetRepositoryEndpoint",
                        "codeartifact:ListPackages",
                        "codeartifact:ListPackageVersions",
                        "codeartifact:ListPackageVersionAssets",
                        "codeartifact:ListPackageVersionDependencies",
                        "codeartifact:ReadFromRepository",
                        "codeartifact:GetDomainPermissionsPolicy",
                        "codeartifact:ListRepositoriesInDomain",
                        "codeartifact:GetAuthorizationToken",
                        "codeartifact:DescribeDomain",
                        "codeartifact:CreateRepository",
                        "sts:GetServiceBearerToken",
                    ],
                    resources=["*"],
                )
            ],
        )
        lake_operational_policy = iam.ManagedPolicy(
            scope=self,
            id="lake_operational_policy",
            managed_policy_name=f"datamaker-{env_name}-{team_name}-user-access",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:*",
                    ],
                    resources=[
                        f"arn:{partition}:s3:::sagemaker-{region}-{self.account}*",
                        self.scratch_bucket.bucket_arn,
                        f"{self.scratch_bucket.bucket_arn}/*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["s3:CreateBucket"],
                    resources=[f"arn:{partition}:s3:::sagemaker*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["ssm:Describe*", "ssm:Get*"],
                    resources=[
                        f"arn:{partition}:ssm:{region}:{self.account}:parameter/datamaker*",
                        f"arn:{partition}:ssm:{region}:{self.account}:parameter/emr_launch/",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["redshift:GetClusterCredentials", "redshift:CreateClusterUser"],
                    resources=[
                        f"arn:{partition}:redshift:{region}:{self.account}:dbuser:{env_name}-{team_name}*",
                        f"arn:{partition}:redshift:{region}:{self.account}:dbuser:{env_name}-{team_name}*/master",
                        f"arn:{partition}:redshift:{region}:{self.account}:dbuser:{env_name}-{team_name}*/defaultdb",
                        f"arn:{partition}:redshift:{region}:{self.account}:dbname:{env_name}-{team_name}*/defaultdb",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "sns:*",
                    ],
                    resources=[
                        f"arn:{partition}:sns:{region}:{self.account}:{env_name}-{team_name}*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["iam:PassRole"],
                    resources=[f"arn:{partition}:iam::{self.account}:role/{lake_role_name}"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["sagemaker:StopNotebookInstance"],
                    resources=[
                        f"arn:{partition}:sagemaker:{region}:{self.account}:notebook-instance/"
                        f"datamaker-{env_name}-{team_name}*"
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "lambda:List*",
                        "lambda:Get*",
                        "iam:List*",
                        "tag:GetResources",
                        "ecr:Get*",
                        "ecr:List*",
                        "ecr:Describe*",
                        "ecr:BatchGetImage",
                        "ecr:BatchCheckLayerAvailability",
                        "cloudwatch:PutMetricData",
                        "redshift:DescribeClusters",
                        "states:List*",
                        "states:Get*",
                        "states:Describe*",
                        "logs:*",
                        "glue:Get*",
                        "glue:List*",
                        "glue:Search*",
                        "athena:*",
                        "events:*",
                        "ecs:Describe*",
                        "ecs:ListTasks",
                        "ec2:Describe*",
                        "redshift:DescribeClusters",
                        "elasticmapreduce:List*",
                        "elasticmapreduce:Get*",
                        "elasticmapreduce:Describe*",
                        "elasticmapreduce:TerminateJobFlows",
                        "elasticmapreduce:AddJobFlowSteps",
                        "sagemaker:List*",
                        "sagemaker:Get*",
                        "personalize:*",
                        "sagemaker:Describe*",
                        "sagemaker:CreateModel",
                        "sagemaker:DeleteModelPackage",
                        "sagemaker:UpdateEndpointWeightsAndCapacities",
                        "sagemaker:DeleteAlgorithm",
                        "sagemaker:Search",
                        "sagemaker:UpdateWorkteam",
                        "sagemaker:UpdateNotebookInstanceLifecycleConfig",
                        "sagemaker:DeleteModel",
                        "sagemaker:CreateModelPackage",
                        "sagemaker:DeleteWorkteam",
                        "sagemaker:CreateEndpoint",
                        "sagemaker:CreateEndpointConfig",
                        "sagemaker:RenderUiTemplate",
                        "sagemaker:StopTransformJob",
                        "sagemaker:CreateLabelingJob",
                        "sagemaker:DeleteEndpointConfig",
                        "sagemaker:CreateAlgorithm",
                        "sagemaker:CreateTrainingJob",
                        "sagemaker:StopHyperParameterTuningJob",
                        "sagemaker:DeleteEndpoint",
                        "sagemaker:CreateTransformJob",
                        "sagemaker:InvokeEndpoint",
                        "sagemaker:CreateWorkteam",
                        "sagemaker:StopLabelingJob",
                        "sagemaker:UpdateEndpoint",
                        "sagemaker:CreateCompilationJob",
                        "sagemaker:StopCompilationJob",
                        "sagemaker:CreateHyperParameterTuningJob",
                        "lakeformation:GetDataAccess",
                    ],
                    resources=["*"],
                ),
            ],
        )

        glue_policy = iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")
        ssm_manage_policy = iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        eks_policies = [
            iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKSWorkerNodePolicy"),
            iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEKS_CNI_Policy"),
            iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name="AmazonEC2ContainerRegistryReadOnly"),
        ]

        managed_policies = [
            lake_operational_policy,
            code_artifact_user_policy,
            glue_policy,
            ssm_manage_policy,
        ] + eks_policies

        user_policies = [iam.ManagedPolicy.from_aws_managed_policy_name(managed_policy_name=self.policy)]

        managed_policies = managed_policies + user_policies

        role = iam.Role(
            scope=self,
            id=lake_role_name,
            role_name=lake_role_name,
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com"),
                iam.ServicePrincipal("glue.amazonaws.com"),
                iam.ServicePrincipal("sagemaker.amazonaws.com"),
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                iam.ServicePrincipal("redshift.amazonaws.com"),
                iam.ServicePrincipal("codepipeline.amazonaws.com"),
                iam.ServicePrincipal("personalize.amazonaws.com"),
            ),
            managed_policies=managed_policies,
        )
        Tags.of(scope=role).add(key="Env", value=f"datamaker-{self.manifest.name}")
        return role

    def _create_sg_efs(self) -> ec2.SecurityGroup:
        name: str = f"datamaker-{self.manifest.name}-{self.team_manifest.name}-efs-sg"
        sg = ec2.SecurityGroup(
            scope=self,
            id=name,
            security_group_name=name,
            vpc=self.i_vpc,
            allow_all_outbound=True,
        )
        for subnet in self.manifest.vpc.subnets:
            if subnet.kind is SubnetKind.private:
                sg.add_ingress_rule(
                    peer=ec2.Peer.ipv4(subnet.cidr_block),
                    connection=ec2.Port.tcp(port=2049),
                    description=f"Allowing internal access from subnet {subnet.subnet_id}.",
                )
        Tags.of(scope=cast(IConstruct, sg)).add(key="Name", value=name)
        Tags.of(scope=cast(IConstruct, sg)).add(key="Env", value=f"datamaker-{self.manifest.name}")
        return sg

    def _create_efs(self) -> efs.FileSystem:
        name: str = f"datamaker-{self.manifest.name}-{self.team_manifest.name}-fs"
        fs = efs.FileSystem(
            scope=self,
            id=name,
            file_system_name=name,
            vpc=self.i_vpc,
            encrypted=False,
            lifecycle_policy=None,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            throughput_mode=efs.ThroughputMode.BURSTING,
            security_group=cast(ec2.ISecurityGroup, self.sg_efs),
            vpc_subnets=ec2.SubnetSelection(subnets=self.i_private_subnets),
        )
        Tags.of(scope=cast(IConstruct, fs)).add(key="Env", value=f"datamaker-{self.manifest.name}")
        return fs

    def _create_user_pool_group(self) -> cognito.CfnUserPoolGroup:
        if self.manifest.user_pool_id is None:
            raise RuntimeError("Empty manifest.user_pool_id")
        return cognito.CfnUserPoolGroup(
            scope=self,
            id=f"{self.team_manifest.name}_group",
            user_pool_id=self.manifest.user_pool_id,
            group_name=self.team_manifest.name,
            description=f"{self.team_manifest.name} users group.",
        )

    def _create_scratch_bucket(self) -> s3.Bucket:
        bucket_name = f"datamaker-{self.team_manifest.env_name}-{self.team_manifest.name}" \
            f"-scratch-{self.manifest.account_id}-{self.manifest.deploy_id}"
        return s3.Bucket(
            scope=self,
            id="scratch_bucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(self.team_manifest.scratch_retention_days))],
        )

    def _create_manifest_parameter(self) -> ssm.StringParameter:
        self.team_manifest.efs_id = self.efs.file_system_id
        self.team_manifest.eks_nodegroup_role_arn = self.role_eks_nodegroup.role_arn
        self.team_manifest.scratch_bucket = self.scratch_bucket.bucket_name

        parameter: ssm.StringParameter = ssm.StringParameter(
            scope=self,
            id=self.team_manifest.ssm_parameter_name,
            string_value=self.team_manifest.repr_full_as_string(),
            type=ssm.ParameterType.STRING,
            description="DataMaker Team Context.",
            parameter_name=self.team_manifest.ssm_parameter_name,
            simple_name=False,
        )
        Tags.of(scope=cast(IConstruct, parameter)).add(key="Env", value=f"datamaker-{self.manifest.name}")
        return parameter


def synth(stack_name: str, filename: str, manifest: Manifest, team_manifest: TeamManifest) -> str:
    filename_dir = path_from_filename(filename=filename)
    outdir = os.path.join(filename_dir, ".datamaker.out", manifest.name, "cdk", stack_name)
    os.makedirs(outdir, exist_ok=True)
    shutil.rmtree(outdir)
    output_filename = os.path.join(outdir, f"{stack_name}.template.json")

    app = App(outdir=outdir)
    Team(scope=app, id=stack_name, manifest=manifest, team_manifest=team_manifest)
    app.synth(force=True)
    return output_filename
