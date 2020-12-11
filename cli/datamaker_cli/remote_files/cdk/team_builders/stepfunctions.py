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

from typing import Dict, List, Union, cast

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_iam as iam
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.aws_stepfunctions_tasks as sfn_tasks
import aws_cdk.core as core
from aws_cdk import aws_lambda

from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.remote_files.cdk.team_builders._lambda import LambdaBuilder
from datamaker_cli.remote_files.cdk.team_builders.stepfunctions_tasks import (
    EcsRunTask,
    EksCall,
    EksRunJob,
    LambdaInvoke,
    LogOptions,
)

COMMAND = ["python", "/opt/python-utils/notebook_cli.py"]


class StateMachineBuilder:
    @staticmethod
    def _build_eks_describe_cluster_task(
        scope: core.Construct,
        lambda_function: aws_lambda.Function,
        cluster_name_path: str = "$.ClusterName",
        result_path: str = "$.DescribeResult",
    ) -> sfn_tasks.LambdaInvoke:
        return LambdaInvoke(
            scope=scope,
            id="EksDescribeCluster",
            lambda_function=lambda_function,
            payload_response_only=True,
            payload=sfn.TaskInput.from_object({"name": sfn.JsonPath.string_at(cluster_name_path)}),
            result_selector={
                "CertificateAuthority.$": "$.cluster.certificateAuthority.data",
                "Endpoint.$": "$.cluster.endpoint",
            },
            result_path=result_path,
        )

    @staticmethod
    def _build_construct_url_task(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        url: str,
        args: Dict[str, Union[str, sfn.JsonPath]],
        result_path: str = "$.UrlResult",
    ) -> sfn_tasks.LambdaInvoke:
        return LambdaInvoke(
            scope=scope,
            id="ConstructUrl",
            lambda_function=LambdaBuilder.get_or_build_construct_url(
                scope=scope, manifest=manifest, team_manifest=team_manifest
            ),
            payload_response_only=True,
            payload=sfn.TaskInput.from_object({"url": url, "args": args}),
            result_path=result_path,
        )

    @staticmethod
    def build_ecs_run_container_state_machine(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        cluster: ecs.Cluster,
        task_definition: ecs.TaskDefinition,
        efs_security_group: ec2.SecurityGroup,
        subnets: List[ec2.ISubnet],
        scratch_bucket: s3.Bucket,
        role: iam.IRole,
    ) -> sfn.StateMachine:
        # We use a nested Construct to avoid collisions with Lambda and Task ids
        construct = core.Construct(scope, "ecs_run_container_nested_construct")

        run_task = EcsRunTask(
            scope=construct,
            id="RunTask",
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            timeout_path="$.Timeout",
            cluster=cluster,
            task_definition=task_definition,
            security_groups=[efs_security_group],
            subnets=ec2.SubnetSelection(subnets=subnets),
            assign_public_ip=True,
            launch_target=cast(
                sfn_tasks.IEcsLaunchTarget,
                sfn_tasks.EcsFargateLaunchTarget(platform_version=ecs.FargatePlatformVersion.VERSION1_4),
            ),
            container_overrides=[
                sfn_tasks.ContainerOverride(
                    container_definition=task_definition.default_container,
                    command=COMMAND,
                    environment=[
                        sfn_tasks.TaskEnvironmentVariable(name="task_type", value=sfn.JsonPath.string_at("$.TaskType")),
                        sfn_tasks.TaskEnvironmentVariable(name="tasks", value=sfn.JsonPath.string_at("$.Tasks")),
                        sfn_tasks.TaskEnvironmentVariable(name="compute", value=sfn.JsonPath.string_at("$.Compute")),
                        sfn_tasks.TaskEnvironmentVariable(name="DATAMAKER_TEAM_SPACE", value=team_manifest.name),
                        sfn_tasks.TaskEnvironmentVariable(name="AWS_DATAMAKER_ENV", value=manifest.name),
                        sfn_tasks.TaskEnvironmentVariable(
                            name="AWS_DATAMAKER_S3_BUCKET", value=scratch_bucket.bucket_name
                        ),
                        sfn_tasks.TaskEnvironmentVariable(
                            name="JUPYTERHUB_USER", value=sfn.JsonPath.string_at("$.JupyterHubUser")
                        ),
                    ],
                )
            ],
        )
        run_task.add_catch(sfn.Fail(scope=construct, id="Failed"))

        definition = sfn.Chain.start(run_task).next(sfn.Succeed(scope=construct, id="Succeeded"))

        return sfn.StateMachine(
            scope=construct,
            id="ecs_run_container_state_machine",
            state_machine_name=f"datamaker-{manifest.name}-{team_manifest.name}-ecs-container-runner",
            definition=definition,
            role=role,
        )

    @staticmethod
    def build_eks_run_container_state_machine(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        image: ecs.EcrImage,
        role: iam.IRole,
    ) -> sfn.StateMachine:
        # We use a nested Construct to avoid collisions with Lambda and Task ids
        construct = core.Construct(scope, "eks_run_container_nested_construct")

        eks_describe_cluster = LambdaBuilder.get_or_build_eks_describe_cluster(
            scope=construct, manifest=manifest, team_manifest=team_manifest
        )
        eks_describe_cluster_task = StateMachineBuilder._build_eks_describe_cluster_task(
            scope=construct,
            lambda_function=eks_describe_cluster,
        )

        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "labels": {"app": "datamaker-jupyterhub"},
                "generateName": "datamaker-runner-",
                "namespace": team_manifest.name,
            },
            "spec": {
                "backoffLimit": 0,
                "template": {
                    "metadata": {
                        "labels": {"app": "datamaker-jupyterhub"},
                        "namespace": team_manifest.name,
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "datamaker-runner",
                                "image": image.image_name,
                                "command": COMMAND,
                                "resources": {
                                    "limits": {
                                        "cpu": f"{team_manifest.container_defaults['cpu']}",
                                        "memory": f"{team_manifest.container_defaults['memory']}M"
                                    },
                                    "requests": {
                                        "cpu": f"{team_manifest.container_defaults['cpu']}",
                                        "memory": f"{team_manifest.container_defaults['memory']}M"
                                    }
                                },
                                "env": [
                                    {"name": "task_type", "value": sfn.JsonPath.string_at("$.TaskType")},
                                    {"name": "tasks", "value": sfn.JsonPath.string_at("$.Tasks")},
                                    {"name": "compute", "value": sfn.JsonPath.string_at("$.Compute")},
                                    {"name": "DATAMAKER_TEAM_SPACE", "value": team_manifest.name},
                                    {"name": "AWS_DATAMAKER_ENV", "value": manifest.name},
                                    {"name": "JUPYTERHUB_USER", "value": sfn.JsonPath.string_at("$.JupyterHubUser")},
                                ],
                                "volumeMounts": [{"name": "efs-volume", "mountPath": "/efs"}],
                            }
                        ],
                        "restartPolicy": "Never",
                        "nodeSelector": {"team": team_manifest.name},
                        "volumes": [{"name": "efs-volume", "persistentVolumeClaim": {"claimName": "jupyterhub"}}],
                    },
                },
            },
        }

        run_job = EksRunJob(
            scope=construct,
            id="RunJob",
            cluster_name=sfn.JsonPath.string_at("$.ClusterName"),
            certificate_authority=sfn.JsonPath.string_at("$.DescribeResult.CertificateAuthority"),
            endpoint=sfn.JsonPath.string_at("$.DescribeResult.Endpoint"),
            namespace=team_manifest.name,
            job=job,
            log_options=LogOptions(retrieve_logs=True, log_parameters={"tailLines": ["20"]}),
            timeout_path="$.Timeout",
        )
        run_job.add_catch(sfn.Fail(scope=construct, id="Failed"))

        definition = (
            sfn.Chain.start(eks_describe_cluster_task).next(run_job).next(sfn.Succeed(scope=construct, id="Succeeded"))
        )

        return sfn.StateMachine(
            scope=construct,
            id="eks_run_container_state_machine",
            state_machine_name=f"datamaker-{manifest.name}-{team_manifest.name}-eks-container-runner",
            definition=definition,
            role=role,
        )

    @staticmethod
    def build_eks_get_pod_logs_state_machine(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        role: iam.IRole,
    ) -> sfn.StateMachine:
        # We use a nested Construct to avoid collisions with Lambda and Task ids
        construct = core.Construct(scope, "eks_get_pod_logs_nested_construct")

        eks_describe_cluster = LambdaBuilder.get_or_build_eks_describe_cluster(
            scope=construct, manifest=manifest, team_manifest=team_manifest
        )
        eks_describe_cluster_task = StateMachineBuilder._build_eks_describe_cluster_task(
            scope=construct,
            lambda_function=eks_describe_cluster,
        )

        construct_url = StateMachineBuilder._build_construct_url_task(
            scope=construct,
            manifest=manifest,
            team_manifest=team_manifest,
            url="/api/v1/namespaces/{namespace}/pods/{pod}/log",
            args={
                "namespace": team_manifest.name,
                "pod": sfn.JsonPath.string_at("$.Pod"),
            },
        )

        eks_call = EksCall(
            scope=construct,
            id="EksCall",
            integration_pattern=sfn.IntegrationPattern.REQUEST_RESPONSE,
            cluster_name=sfn.JsonPath.string_at("$.ClusterName"),
            certificate_authority=sfn.JsonPath.string_at("$.DescribeResult.CertificateAuthority"),
            endpoint=sfn.JsonPath.string_at("$.DescribeResult.Endpoint"),
            method="GET",
            path=sfn.JsonPath.string_at("$.UrlResult"),
            query_parameters={"tailLines": ["20"]},
        )

        definition = (
            sfn.Chain.start(eks_describe_cluster_task)
            .next(construct_url)
            .next(eks_call)
            .next(sfn.Succeed(scope=construct, id="Succeeded"))
        )

        return sfn.StateMachine(
            scope=construct,
            id="eks_get_pod_logs_state_machine",
            state_machine_name=f"datamaker-{manifest.name}-{team_manifest.name}-get-pod-logs",
            state_machine_type=sfn.StateMachineType.EXPRESS,
            definition=definition,
            role=role,
        )
