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

from typing import Any, Dict, List, cast

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_iam as iam
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.aws_stepfunctions_tasks as sfn_tasks
import aws_cdk.core as core
from aws_cdk import aws_lambda
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.remote_files.cdk.team_builders._lambda import LambdaBuilder
from aws_orbit.remote_files.cdk.team_builders.stepfunctions_tasks import (
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
    def _build_construct_request_task(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        namespace: str,
        result_path: str = "$.RequestResult",
    ) -> sfn_tasks.LambdaInvoke:
        return LambdaInvoke(
            scope=scope,
            id="ConstructRequest",
            lambda_function=LambdaBuilder.get_or_build_construct_request(
                scope=scope, manifest=manifest, team_manifest=team_manifest
            ),
            payload_response_only=True,
            payload=sfn.TaskInput.from_object(
                {
                    "ExecutionInput": sfn.TaskInput.from_context_at("$$.Execution.Input").value,
                    "Namespace": namespace,
                }
            ),
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
                        sfn_tasks.TaskEnvironmentVariable(name="ORBIT_TEAM_SPACE", value=team_manifest.name),
                        sfn_tasks.TaskEnvironmentVariable(name="AWS_ORBIT_ENV", value=manifest.name),
                        sfn_tasks.TaskEnvironmentVariable(name="AWS_ORBIT_S3_BUCKET", value=scratch_bucket.bucket_name),
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
            state_machine_name=f"orbit-{manifest.name}-{team_manifest.name}-ecs-container-runner",
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
        node_type: str,
    ) -> sfn.StateMachine:
        if node_type not in {"ec2", "fargate"}:
            raise ValueError(f"Invalid node_type: {node_type}")

        # We use a nested Construct to avoid collisions with Lambda and Task ids
        construct = core.Construct(scope, f"eks_run_{node_type}_container_nested_construct")

        eks_describe_cluster = LambdaBuilder.get_or_build_eks_describe_cluster(
            scope=construct, manifest=manifest, team_manifest=team_manifest
        )
        eks_describe_cluster_task = StateMachineBuilder._build_eks_describe_cluster_task(
            scope=construct,
            lambda_function=eks_describe_cluster,
        )

        job: Dict[str, Any] = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "labels": {"app": f"orbit-{team_manifest.name}-{node_type}-runner"},
                "generateName": f"orbit-{team_manifest.name}-{node_type}-runner-",
                "namespace": team_manifest.name,
            },
            "spec": {
                "backoffLimit": 0,
                "activeDeadlineSeconds": sfn.JsonPath.number_at("$.Timeout"),
                "ttlSecondsAfterFinished": 120,
                "template": {
                    "metadata": {
                        "labels": {"app": f"orbit-{team_manifest.name}-runner", "team": team_manifest.name},
                        "namespace": team_manifest.name,
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "orbit-runner",
                                "image": image.image_name,
                                "command": COMMAND,
                                "securityContext": {
                                    "runAsUser": 1000,
                                },
                                "resources": {
                                    "limits": {
                                        "cpu": sfn.JsonPath.string_at("$.CPU"),
                                        "memory": sfn.JsonPath.string_at("$.Memory"),
                                    },
                                    "requests": {
                                        "cpu": sfn.JsonPath.string_at("$.CPU"),
                                        "memory": sfn.JsonPath.string_at("$.Memory"),
                                    },
                                },
                                "env": [
                                    {"name": "task_type", "value": sfn.JsonPath.string_at("$.TaskType")},
                                    {"name": "tasks", "value": sfn.JsonPath.string_at("$.Tasks")},
                                    {"name": "compute", "value": sfn.JsonPath.string_at("$.Compute")},
                                    {"name": "ORBIT_TEAM_SPACE", "value": team_manifest.name},
                                    {"name": "AWS_ORBIT_ENV", "value": manifest.name},
                                    {"name": "JUPYTERHUB_USER", "value": sfn.JsonPath.string_at("$.JupyterHubUser")},
                                ],
                                "volumeMounts": [{"name": "efs-volume", "mountPath": "/efs"}],
                            }
                        ],
                        "restartPolicy": "Never",
                        "volumes": [{"name": "efs-volume", "persistentVolumeClaim": {"claimName": "jupyterhub"}}],
                    },
                },
            },
        }

        if node_type == "ec2":
            job["spec"]["template"]["spec"]["nodeSelector"] = {
                "team": team_manifest.name,
                "orbit/compute-type": "ec2",
            }
        elif node_type == "fargate":
            job["spec"]["template"]["spec"]["serviceAccountName"] = team_manifest.name
            job["spec"]["template"]["spec"]["securityContext"] = {"fsGroup": 1000}
            job["spec"]["template"]["metadata"]["labels"]["orbit/compute-type"] = "fargate"

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
            result_path="$.RunJobResult",
        )
        run_job.add_catch(sfn.Fail(scope=construct, id="Failed"))

        # We generate the arn of the k8s api state machine to eliminate a circular reference created
        # when we attempt to use a StateMachine Construct. The reference occurs because both state
        # machines use the same Role
        k8s_api_state_machine = sfn.StateMachine.from_state_machine_arn(
            scope=construct,
            id="K8sApiStateMachine",
            state_machine_arn=(
                f"arn:{core.Aws.PARTITION}:states:{core.Aws.REGION}:"
                f"{core.Aws.ACCOUNT_ID}:stateMachine:orbit-{manifest.name}-{team_manifest.name}-eks-k8s-api"
            ),
        )
        delete_job = sfn_tasks.StepFunctionsStartExecution(
            scope=construct,
            id="DeleteJob",
            state_machine=k8s_api_state_machine,
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            input=sfn.TaskInput.from_object(
                {
                    "ClusterName": sfn.JsonPath.string_at("$.ClusterName"),
                    "Method": "DELETE",
                    "Api": "batch",
                    "Path": "/jobs/{job}",
                    "PathArgs": {"job": sfn.JsonPath.string_at("$.RunJobResult.metadata.name")},
                    "QueryParameters": {"propagationPolicy": ["Background"]},
                }
            ),
            result_path="$.DeleteJobResult",
        )

        definition = (
            sfn.Chain.start(eks_describe_cluster_task)
            .next(run_job)
            .next(delete_job)
            .next(sfn.Succeed(scope=construct, id="Succeeded"))
        )

        return sfn.StateMachine(
            scope=construct,
            id="eks_run_container_state_machine",
            state_machine_name=f"orbit-{manifest.name}-{team_manifest.name}-eks-{node_type}-container-runner",
            definition=definition,
            role=role,
        )

    @staticmethod
    def build_eks_k8s_api_state_machine(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        role: iam.Role,
    ) -> sfn.StateMachine:
        # We use a nested Construct to avoid collisions with Lambda and Task ids
        construct = core.Construct(scope, "eks_k8s_api_nested_construct")

        eks_describe_cluster = LambdaBuilder.get_or_build_eks_describe_cluster(
            scope=construct, manifest=manifest, team_manifest=team_manifest
        )
        eks_describe_cluster_task = StateMachineBuilder._build_eks_describe_cluster_task(
            scope=construct,
            lambda_function=eks_describe_cluster,
        )

        construct_request = StateMachineBuilder._build_construct_request_task(
            scope=construct,
            manifest=manifest,
            team_manifest=team_manifest,
            namespace=team_manifest.name,
        )

        eks_call = EksCall(
            scope=construct,
            id="EksCall",
            integration_pattern=sfn.IntegrationPattern.REQUEST_RESPONSE,
            cluster_name=sfn.JsonPath.string_at("$.ClusterName"),
            certificate_authority=sfn.JsonPath.string_at("$.DescribeResult.CertificateAuthority"),
            endpoint=sfn.JsonPath.string_at("$.DescribeResult.Endpoint"),
            method=sfn.JsonPath.string_at("$.RequestResult.Method"),
            path=sfn.JsonPath.string_at("$.RequestResult.Path"),
            query_parameters=sfn.JsonPath.string_at("$.RequestResult.QueryParameters"),
            request_body=sfn.TaskInput.from_data_at("$.RequestResult.RequestBody").value,
        )

        definition = (
            sfn.Chain.start(eks_describe_cluster_task)
            .next(construct_request)
            .next(eks_call)
            .next(sfn.Succeed(scope=construct, id="Succeeded"))
        )

        return sfn.StateMachine(
            scope=construct,
            id="eks_k8s_api_state_machine",
            state_machine_name=f"orbit-{manifest.name}-{team_manifest.name}-eks-k8s-api",
            state_machine_type=sfn.StateMachineType.EXPRESS,
            definition=definition,
            role=role,
        )
