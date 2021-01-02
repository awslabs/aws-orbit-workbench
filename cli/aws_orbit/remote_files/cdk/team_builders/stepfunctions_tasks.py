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

import abc
import functools
from typing import Any, Callable, Dict, List, Mapping, Optional, Union, cast

import aws_cdk.aws_iam as iam
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.aws_stepfunctions_tasks as sfn_tasks
import aws_cdk.core as core


class LogOptions:
    def __init__(
        self, *, retrieve_logs: bool = False, raw_logs: bool = False, log_parameters: Optional[Dict[str, Any]] = None
    ) -> None:
        self.retrieve_logs = retrieve_logs
        self.raw_logs = raw_logs
        self.log_parameters = log_parameters

    def render(self) -> Mapping[Any, Any]:
        log_options = {
            "RawLogs": self.raw_logs,
            "RetrieveLogs": self.retrieve_logs,
            "LogParameters": self.log_parameters,
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
        timeout_path: Optional[str] = None,
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
            timeout=timeout,
        )

        self._heartbeat = heartbeat
        self._heartbeat_path = heartbeah_path
        self._result_selector = result_selector
        self._timeout = timeout
        self._timeout_path = timeout_path

    @staticmethod
    def get_resource_arn(service: str, api: str, integration_pattern: sfn.IntegrationPattern) -> str:
        if not service or not api:
            raise ValueError("Both 'service' and 'api' are required to build the resource ARN")

        resource_arn_suffixes = {
            sfn.IntegrationPattern.REQUEST_RESPONSE: "",
            sfn.IntegrationPattern.RUN_JOB: ".sync",
            sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN: ".waitForTaskToken",
        }

        return f"arn:{core.Aws.PARTITION}:states:::{service}:{api}{resource_arn_suffixes[integration_pattern]}"

    @staticmethod
    def render_json_path(json_path: str) -> Optional[str]:
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
            "TimeoutSecondsPath": self.render_json_path(cast(str, self._timeout_path)),
            "HeartbeatSeconds": self._heartbeat.to_seconds() if self._heartbeat else None,
            "HeartbeatSecondsPath": self.render_json_path(cast(str, self._heartbeat_path)),
            "InputPath": self.render_json_path(self._input_path),
            "OutputPath": self.render_json_path(self._output_path),
            "ResultPath": self.render_json_path(self._result_path),
            "ResultSelector": self._result_selector,
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
        timeout_path: Optional[str] = None,
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
            timeout_path=timeout_path,
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
                    "eks:DescribeCluster",
                ],
                resources=["*"],
            )
        ]

    def _task_metrics(self) -> Optional[sfn.TaskMetricsConfig]:
        return self._metrics

    def _task_policies(self) -> List[iam.PolicyStatement]:
        return self._statements

    def to_state_json(self) -> Mapping[Any, Any]:
        task = {
            "Resource": self.get_resource_arn("eks", "runJob", self._integration_pattern),
            "Parameters": sfn.FieldUtils.render_object(
                {
                    "ClusterName": self._cluster_name,
                    "CertificateAuthority": self._certificate_authority,
                    "Endpoint": self._endpoint,
                    "Job": self._job,
                    "Namespace": self._namespace,
                    "LogOptions": self._log_options.render() if self._log_options else None,
                }
            ),
        }
        task.update(self._render_next_end())
        task.update(self._render_retry_catch())
        task.update(self._render_task_base())
        return task


class EksCall(BaseTask):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        *,
        cluster_name: str,
        certificate_authority: str,
        endpoint: str,
        path: str,
        method: str = "Get",
        query_parameters: Optional[Dict[str, List[str]]] = None,
        request_body: Optional[Union[str, Mapping[Any, Any]]] = None,
        comment: Optional[str] = None,
        heartbeat: Optional[core.Duration] = None,
        heartbeah_path: Optional[str] = None,
        input_path: Optional[str] = None,
        integration_pattern: Optional[sfn.IntegrationPattern] = None,
        output_path: Optional[str] = None,
        result_path: Optional[str] = None,
        result_selector: Optional[Dict[str, str]] = None,
        timeout: Optional[core.Duration] = None,
        timeout_path: Optional[str] = None,
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
            timeout_path=timeout_path,
        )
        self._cluster_name = cluster_name
        self._certificate_authority = certificate_authority
        self._endpoint = endpoint
        self._integration_pattern = integration_pattern if integration_pattern else sfn.IntegrationPattern.RUN_JOB
        self._method = method
        self._path = path
        self._query_parameters = query_parameters
        self._request_body = request_body
        self._metrics = None
        self._statements = self._create_policy_statements()

    def _create_policy_statements(self) -> List[iam.PolicyStatement]:
        return [
            iam.PolicyStatement(
                actions=[
                    "eks:DescribeCluster",
                ],
                resources=["*"],
            )
        ]

    def _task_metrics(self) -> Optional[sfn.TaskMetricsConfig]:
        return self._metrics

    def _task_policies(self) -> List[iam.PolicyStatement]:
        return self._statements

    def to_state_json(self) -> Mapping[Any, Any]:
        task = {
            "Resource": self.get_resource_arn("eks", "call", self._integration_pattern),
            "Parameters": sfn.FieldUtils.render_object(
                {
                    "ClusterName": self._cluster_name,
                    "CertificateAuthority": self._certificate_authority,
                    "Endpoint": self._endpoint,
                    "Method": self._method,
                    "Path": self._path,
                    "QueryParameters": self._query_parameters,
                    "RequestBody": self._request_body,
                }
            ),
        }
        task.update(self._render_next_end())
        task.update(self._render_retry_catch())
        task.update(self._render_task_base())
        return task


class IExtendedTaskStateBase:
    @abc.abstractmethod
    def __init__(
        self,
        *args: Any,
        heartbeat_path: Optional[str] = None,
        result_selector: Optional[Dict[str, str]] = None,
        timeout_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        pass


def extended_task(_class: Any) -> Callable[[Any, Any], IExtendedTaskStateBase]:
    def render_json_path(json_path: str) -> Optional[str]:
        if json_path is None:
            return None
        elif json_path == sfn.JsonPath.DISCARD:
            return None

        if not json_path.startswith("$"):
            raise ValueError(f"Expected JSON path to start with '$', got: {json_path}")

        return json_path

    def to_state_json(self: Any) -> Any:
        task = self._to_state_json()
        if self._heartbeat_path:
            task["HeartbeatSecondsPath"] = self.render_json_path(self._heartbeat_path)
        if self._result_selector:
            task["ResultSelector"] = self._result_selector
        if self._timeout_path:
            task["TimeoutSecondsPath"] = self.render_json_path(self._timeout_path)
        return task

    @functools.wraps(_class)
    def wrapper_extended_task(*args: Any, **kwargs: Any) -> IExtendedTaskStateBase:
        if "_have_extended_task" not in dir(_class):
            _class._have_extended_task = True
            _class.render_json_path = staticmethod(render_json_path)

            _class._to_state_json = _class.to_state_json
            _class.to_state_json = to_state_json

        heartbeat_path = kwargs.pop("heartbeat_path") if "heartbeat_path" in kwargs else None
        result_selector = kwargs.pop("result_selector") if "result_selector" in kwargs else None
        timeout_path = kwargs.pop("timeout_path") if "timeout_path" in kwargs else None

        inst = _class(*args, **kwargs)
        inst._heartbeat_path = heartbeat_path
        inst._result_selector = result_selector
        inst._timeout_path = timeout_path
        return cast(IExtendedTaskStateBase, inst)

    return wrapper_extended_task


@extended_task
class EcsRunTask(sfn_tasks.EcsRunTask, IExtendedTaskStateBase):
    def __init__(
        self,
        *args: Any,
        heartbeat_path: Optional[str] = None,
        result_selector: Optional[Dict[str, str]] = None,
        timeout_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)


@extended_task
class LambdaInvoke(sfn_tasks.LambdaInvoke, IExtendedTaskStateBase):
    def __init__(
        self,
        *args: Any,
        heartbeat_path: Optional[str] = None,
        result_selector: Optional[Dict[str, str]] = None,
        timeout_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
