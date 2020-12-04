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

import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_iam as iam
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.aws_stepfunctions_tasks as sfn_tasks
import aws_cdk.core as core

from aws_cdk import aws_lambda
from typing import Any, Dict, List, Mapping, Optional
from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.remote_files.cdk.team_builders._lambda import LambdaBuilder


COMMAND = ["python", "/opt/python-utils/notebook_cli.py"]


class LogOptions:
    def __init__(
        self,
        *,
        retrieve_logs: bool = False,
        raw_logs: bool = False,
        log_parameters: Optional[Dict[str, str]] = None
    ) -> None:
        self.retrieve_logs = retrieve_logs
        self.raw_logs = raw_logs
        self.log_parameters = log_parameters

    def render(self) -> Mapping[Any, Any]:
        log_options = {
            "RawLogs": self.raw_logs,
            "RetrieveLogs": self.retrieve_logs,
            "LogParameters": self.log_parameters
        }
        return {k: v for k, v in log_options.items() if v is not None}


class BaseTask(sfn.TaskStateBase):

    def __init__(
        self,
        scope: core.Construct,
        id: str,
        *,
        comment: Optional[str] = None,
        heartbeat: Optional[core.Duration] = None,
        heartbeah_path: Optional[str] = None,
        input_path: Optional[str] = None,
        integration_pattern: Optional[sfn.IntegrationPattern] = None,
        output_path: Optional[str] = None,
        result_path: Optional[str] = None,
        result_selector: Optional[Dict[str, str]] = None,
        timeout: Optional[core.Duration] = None,
        timeout_path: Optional[str] = None
    ) -> None:
        super().__init__(
            scope=scope,
            id=id,
            comment=comment,
            heartbeat=heartbeat,
            input_path=input_path,
            integration_pattern=integration_pattern,
            output_path=output_path,
            result_path=result_path,
            timeout=timeout)

        self._heartbeat = heartbeat
        self._heartbeat_path = heartbeah_path
        self._result_selector = result_selector
        self._timeout = timeout
        self._timeout_path = timeout_path

    @staticmethod
    def get_resource_arn(
            service: str, api: str,
            integration_pattern: Optional[sfn.IntegrationPattern] = sfn.IntegrationPattern.RUN_JOB) -> str:
        if not service or not api:
            raise ValueError("Both 'service' and 'api' are required to build the resource ARN")

        resource_arn_suffixes = {
            sfn.IntegrationPattern.REQUEST_RESPONSE: "",
            sfn.IntegrationPattern.RUN_JOB: ".sync",
            sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN: ".waitForTaskToken"
        }

        return f"arn:{core.Aws.PARTITION}:states:::{service}:{api}{resource_arn_suffixes[integration_pattern]}"

    @staticmethod
    def render_json_path(json_path: str) -> str:
        if json_path is None:
            return None
        elif json_path == sfn.JsonPath.DISCARD:
            return None

        if not json_path.startswith("$"):
            raise ValueError(f"Expected JSON path to start with '$', got: {json_path}")

        return json_path

    def _render_task_base(self) -> Mapping[Any, Any]:
        task = {
            "Type": "Task",
            "Comment": self._comment,
            "TimeoutSeconds": self._timeout.to_seconds() if self._timeout else None,
            "TimeoutSecondsPath": self.render_json_path(self._timeout_path),
            "HeartbeatSeconds": self._heartbeat.to_seconds() if self._heartbeat else None,
            "HeartbeatSecondsPath": self.render_json_path(self._heartbeat_path),
            "InputPath": self.render_json_path(self._input_path),
            "OutputPath": self.render_json_path(self._output_path),
            "ResultPath": self.render_json_path(self._result_path),
            "ResultSelector": self._result_selector
        }
        return {k: v for k, v in task.items() if v is not None}

    def _when_bound_to_graph(self, graph: sfn.StateGraph) -> None:
        super()._when_bound_to_graph(graph)
        for policy_statement in self._task_policies():
            graph.register_policy_statement(policy_statement)


class EksRunJob(BaseTask):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        *,
        cluster_name: str,
        certificate_authority: str,
        endpoint: str,
        namespace: str = "default",
        job: Mapping[Any, Any],
        log_options: Optional[LogOptions] = None,
        comment: Optional[str] = None,
        heartbeat: Optional[core.Duration] = None,
        heartbeah_path: Optional[str] = None,
        input_path: Optional[str] = None,
        integration_pattern: Optional[sfn.IntegrationPattern] = None,
        output_path: Optional[str] = None,
        result_path: Optional[str] = None,
        result_selector: Optional[Dict[str, str]] = None,
        timeout: Optional[core.Duration] = None,
        timeout_path: Optional[str] = None
    ) -> None:
        super().__init__(
            scope=scope,
            id=id,
            comment=comment,
            heartbeat=heartbeat,
            heartbeah_path=heartbeah_path,
            input_path=input_path,
            integration_pattern=integration_pattern,
            output_path=output_path,
            result_path=result_path,
            result_selector=result_selector,
            timeout=timeout,
            timeout_path=timeout_path
        )
        self._cluster_name = cluster_name
        self._certificate_authority = certificate_authority
        self._endpoint = endpoint
        self._namespace = namespace
        self._integration_pattern = integration_pattern if integration_pattern else sfn.IntegrationPattern.RUN_JOB
        self._job = job
        self._log_options = log_options
        self._metrics = None
        self._statements = self._create_policy_statements()

    def _create_policy_statements(self) -> List[iam.PolicyStatement]:
        return [
            iam.PolicyStatement(
                actions=[
                    'eks:DescribeCluster',
                ],
                resources=['*']
            )
        ]

    def _task_metrics(self) -> Optional[sfn.TaskMetricsConfig]:
        return self._metrics

    def _task_policies(self) -> List[iam.PolicyStatement]:
        return self._statements

    def to_state_json(self) -> Mapping[Any, Any]:
        task = {
            "Resource": self.get_resource_arn("eks", "runJob", self._integration_pattern),
            "Parameters": sfn.FieldUtils.render_object({
                "ClusterName": self._cluster_name,
                "CertificateAuthority": self._certificate_authority,
                "Endpoint": self._endpoint,
                "Job": self._job,
                "Namespace": self._namespace,
                "LogOptions": self._log_options.render() if self._log_options else None,
            }),
        }
        task.update(self._render_next_end())
        task.update(self._render_retry_catch())
        task.update(self._render_task_base())
        return task


class EcsRunTask(sfn_tasks.EcsRunTask):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        *,
        cluster: ecs.ICluster,
        launch_target: sfn_tasks.IEcsLaunchTarget,
        task_definition: ecs.TaskDefinition,
        assign_public_ip: Optional[bool] = None,
        container_overrides: Optional[List[sfn_tasks.ContainerOverride]] = None,
        security_groups: Optional[List[ec2.ISecurityGroup]] = None,
        subnets: Optional[ec2.SubnetSelection] = None,
        comment: Optional[str] = None,
        heartbeat: Optional[core.Duration] = None,
        heartbeah_path: Optional[str] = None,
        input_path: Optional[str] = None,
        integration_pattern: Optional[sfn.IntegrationPattern] = None,
        output_path: Optional[str] = None,
        result_path: Optional[str] = None,
        result_selector: Optional[Dict[str, str]] = None,
        timeout: Optional[core.Duration] = None,
        timeout_path: Optional[str] = None
    ) -> None:
        super().__init__(
            scope=scope,
            id=id,
            cluster=cluster,
            launch_target=launch_target,
            task_definition=task_definition,
            assign_public_ip=assign_public_ip,
            container_overrides=container_overrides,
            security_groups=security_groups,
            subnets=subnets,
            comment=comment,
            heartbeat=heartbeat,
            input_path=input_path,
            integration_pattern=integration_pattern,
            output_path=output_path,
            result_path=result_path,
            timeout=timeout
        )
        self._heartbeat_path = heartbeah_path
        self._result_selector = result_selector
        self._timeout_path = timeout_path

    @staticmethod
    def render_json_path(json_path: str) -> str:
        if json_path is None:
            return None
        elif json_path == sfn.JsonPath.DISCARD:
            return None

        if not json_path.startswith("$"):
            raise ValueError(f"Expected JSON path to start with '$', got: {json_path}")

        return json_path

    def to_state_json(self) -> Mapping[Any, Any]:
        task = super().to_state_json()
        if self._heartbeat_path:
            task["HeartbeatSecondsPath"] = self.render_json_path(self._heartbeat_path)
        if self._result_selector:
            task["ResultSelector"] = self._result_selector
        if self._timeout_path:
            task["TimeoutSecondsPath"] = self.render_json_path(self._timeout_path)
        return task


class LambdaInvoke(sfn_tasks.LambdaInvoke):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        *,
        lambda_function: aws_lambda.IFunction,
        client_context: Optional[str] = None,
        invocation_type: Optional[sfn_tasks.LambdaInvocationType] = None,
        payload: Optional[sfn.TaskInput] = None,
        payload_response_only: Optional[bool] = None,
        qualifier: Optional[str] = None,
        retry_on_service_exceptions: Optional[bool] = None,
        comment: Optional[str] = None,
        heartbeat: Optional[core.Duration] = None,
        heartbeah_path: Optional[str] = None,
        input_path: Optional[str] = None,
        integration_pattern: Optional[sfn.IntegrationPattern] = None,
        output_path: Optional[str] = None,
        result_path: Optional[str] = None,
        result_selector: Optional[Dict[str, str]] = None,
        timeout: Optional[core.Duration] = None,
        timeout_path: Optional[str] = None
    ) -> None:
        super().__init__(
            scope=scope,
            id=id,
            lambda_function=lambda_function,
            client_context=client_context,
            invocation_type=invocation_type,
            payload=payload,
            payload_response_only=payload_response_only,
            qualifier=qualifier,
            retry_on_service_exceptions=retry_on_service_exceptions,
            comment=comment,
            heartbeat=heartbeat,
            input_path=input_path,
            integration_pattern=integration_pattern,
            output_path=output_path,
            result_path=result_path,
            timeout=timeout
        )
        self._heartbeat_path = heartbeah_path
        self._result_selector = result_selector
        self._timeout_path = timeout_path

    @staticmethod
    def render_json_path(json_path: str) -> str:
        if json_path is None:
            return None
        elif json_path == sfn.JsonPath.DISCARD:
            return None

        if not json_path.startswith("$"):
            raise ValueError(f"Expected JSON path to start with '$', got: {json_path}")

        return json_path

    def to_state_json(self) -> Mapping[Any, Any]:
        task = super().to_state_json()
        if self._heartbeat_path:
            task["HeartbeatSecondsPath"] = self.render_json_path(self._heartbeat_path)
        if self._result_selector:
            task["ResultSelector"] = self._result_selector
        if self._timeout_path:
            task["TimeoutSecondsPath"] = self.render_json_path(self._timeout_path)
        return task


# def ExtendTask(task: sfn.TaskStateBase) -> None:
#     def set_heartbeat_path(self, value: str) -> None:
#         self._heartbeat_path = value

#     def set_result_selector(self, value: Dict[str, str]) -> None:
#         self._result_selector = value

#     def set_timeout_path(self, value: str) -> None:
#         self._timeout_path = value

#     @staticmethod
#     def render_json_path(json_path: str) -> str:
#         if json_path is None:
#             return None
#         elif json_path == sfn.JsonPath.DISCARD:
#             return None

#         if not json_path.startswith("$"):
#             raise ValueError(f"Expected JSON path to start with '$', got: {json_path}")

#         return json_path

#     def to_state_json(self) -> Mapping[Any, Any]:
#         task = self._to_state_json()
#         if self._heartbeat_path:
#             task["HeartbeatSecondsPath"] = self.render_json_path(self._heartbeat_path)
#         if self._result_selector:
#             task["ResultSelector"] = self._result_selector
#         if self._timeout_path:
#             task["TimeoutSecondsPath"] = self.render_json_path(self._timeout_path)
#         _logger.info(f"Task State Json: {task}")
#         return task

#     task.set_heartbeat_path = set_heartbeat_path
#     task.set_result_selector = set_result_selector
#     task.set_timeout_path = set_timeout_path
#     task.render_json_path = render_json_path
#     task._to_state_json = task.to_state_json
#     task.to_state_json = to_state_json

# ExtendTask(sfn_tasks.EcsRunTask)
# ExtendTask(sfn_tasks.LambdaInvoke)


class StateMachineBuilder:
    @staticmethod
    def build_ecs_run_container_state_machine(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        cluster: ecs.Cluster,
        task_definition: ecs.TaskDefinition,
        efs_security_group: ec2.SecurityGroup,
        subnets: List[ec2.ISubnet],
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
            launch_target=sfn_tasks.EcsFargateLaunchTarget(platform_version=ecs.FargatePlatformVersion.VERSION1_4),
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
                        sfn_tasks.TaskEnvironmentVariable(name="JUPYTERHUB_USER", value=sfn.JsonPath.string_at("$.JupyterHubUser")),
                    ]
                )
            ],
        )
        # run_task.set_timeout_path("$.Timeout")
        run_task.add_catch(sfn.Fail(scope=construct, id="Failed"))

        definition = sfn.Chain \
            .start(run_task) \
            .next(sfn.Succeed(scope=construct, id="Succeeded"))

        return sfn.StateMachine(
            scope=construct,
            id="ecs_run_container_state_machine",
            state_machine_name=f"datamaker-{manifest.name}-{team_manifest.name}-ecs-container-runner",
            definition=definition,
            role=role
        )

    def build_eks_run_container_state_machine(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
        image: ecs.EcrImage,
        role: iam.IRole,
    ) -> sfn.StateMachine:
        # We use a nested Construct to avoid collisions with Lambda and Task ids
        construct = core.Construct(scope, "eks_run_container_nested_construct")

        eks_describe_cluster = LambdaInvoke(
            scope=construct,
            id="EksDescribeCluster",
            lambda_function=LambdaBuilder.build_eks_describe_cluster(
                scope=scope,
                manifest=manifest,
                team_manifest=team_manifest
            ),
            payload_response_only=True,
            payload=sfn.TaskInput.from_object({
                "name": sfn.JsonPath.string_at("$.ClusterName")
            }),
            result_selector={
                "CertificateAuthority.$": "$.cluster.certificateAuthority.data",
                "Endpoint.$": "$.cluster.endpoint"
            },
            result_path="$.DescribeResult"
        )

        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "labels": {
                    "app": "datamaker-jupyterhub"
                },
                "generateName": "datamaker-runner-",
                "namespace": team_manifest.name
            },
            "spec": {
                "backoffLimit": 0,
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "datamaker-jupyterhub"
                        },
                        "namespace": team_manifest.name,
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "datamaker-runner",
                                "image": image.image_name,
                                "command": COMMAND,
                                "env": [
                                    {"name": "task_type", "value": sfn.JsonPath.string_at("$.TaskType")},
                                    {"name": "tasks", "value": sfn.JsonPath.string_at("$.Tasks")},
                                    {"name": "compute", "value": sfn.JsonPath.string_at("$.Compute")},
                                    {"name": "DATAMAKER_TEAM_SPACE", "value": team_manifest.name},
                                    {"name": "AWS_DATAMAKER_ENV", "value": manifest.name},
                                    {"name": "JUPYTERHUB_USER", "value": sfn.JsonPath.string_at("$.JupyterHubUser")},
                                ],
                                "volumeMounts":[
                                    {"name": "efs-volume", "mountPath": "/efs"}
                                ]
                            }
                        ],
                        "restartPolicy": "Never",
                        "nodeSelector": {
                            "team": team_manifest.name
                        },
                        "volumes": [
                            {
                                "name": "efs-volume",
                                "persistentVolumeClaim": {
                                    "claimName": "jupyterhub"
                                }
                            }
                        ]
                    }
                }
            }
        }

        run_job = EksRunJob(
            scope=construct,
            id="RunJob",
            cluster_name=sfn.JsonPath.string_at("$.ClusterName"),
            certificate_authority=sfn.JsonPath.string_at("$.DescribeResult.CertificateAuthority"),
            endpoint=sfn.JsonPath.string_at("$.DescribeResult.Endpoint"),
            namespace=team_manifest.name,
            job=job,
            log_options=LogOptions(retrieve_logs=True),
            timeout_path="$.Timeout"
        )
        run_job.add_catch(sfn.Fail(scope=construct, id="Failed"))

        definition = sfn.Chain \
            .start(eks_describe_cluster) \
            .next(run_job) \
            .next(sfn.Succeed(scope=construct, id="Succeeded"))

        return sfn.StateMachine(
            scope=construct,
            id="eks_run_container_state_machine",
            state_machine_name=f"datamaker-{manifest.name}-{team_manifest.name}-eks-container-runner",
            definition=definition,
            role=role
        )