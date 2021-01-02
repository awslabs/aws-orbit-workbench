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

import json
import logging
import os
from time import sleep
from typing import Any, Dict, Optional

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


sfn = boto3.client("stepfunctions")

MAX_EXECUTION_HISTORY_ATTEMPTS = 5


def _get_event_output(execution_arn: str, event_type: str, event_id: int, details_key: str) -> Any:
    event_details_key = event_type[0].lower() + event_type[1:] + "EventDetails"
    return_val = None
    attempts = 0
    sleep_time = 1
    backoff_factor = 1.6

    while return_val is None:
        sleep(sleep_time)
        response = sfn.get_execution_history(
            executionArn=execution_arn,
            reverseOrder=True,
            maxResults=1000,
        )
        events = response["events"]

        attempts += 1
        sleep_time = round(sleep_time * backoff_factor)
        max_event_id = 0

        for event in events:
            id = event["id"]
            type = event["type"]
            max_event_id = max(max_event_id, id)

            if id == event_id and type == event_type:
                details = event[event_details_key]
                return_val = details.get(details_key, "")
                break
            elif type == "ExecutionFailed":
                raise Exception(
                    f"ExecutionFailed: {event['executionFailedEventDetails'].get('cause', 'Unknown error')}"
                )

        if return_val is not None:
            break
        elif max_event_id > event_id or attempts >= MAX_EXECUTION_HISTORY_ATTEMPTS:
            raise Exception(
                f"Event not found. The event_type ({event_type}) and event_id ({event_id}) combination was not found."
            )

    return return_val


def _start_ecs_fargate(event: Dict[str, Any], execution_vars: Dict[str, Any]) -> Dict[str, str]:
    logger.info(f"start_ecs_fargate: {json.dumps(execution_vars)}")

    state_machine_arn = os.environ["ECS_FARGATE_STATE_MACHINE_ARN"]
    response = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps(execution_vars),
    )

    execution_arn = response["executionArn"]
    output = json.loads(
        _get_event_output(execution_arn=execution_arn, event_type="TaskSubmitted", event_id=5, details_key="output")
    )

    return {"ExecutionType": "ecs", "ExecutionArn": execution_arn, "Identifier": output["Tasks"][0]["TaskArn"]}


def _start_ecs_ec2(event: Dict[str, Any], execution_vars: Dict[str, Any]) -> Dict[str, str]:
    logger.info(f"start_ecs_ec2: {json.dumps(execution_vars)}")
    raise NotImplementedError("ECS/EC2 Execution not yet implemented")


def _start_eks_fargate(event: Dict[str, Any], execution_vars: Dict[str, Any]) -> Dict[str, str]:
    logger.info(f"start_eks_fargate: {json.dumps(execution_vars)}")

    state_machine_arn = os.environ["EKS_FARGATE_STATE_MACHINE_ARN"]
    response = sfn.start_execution(stateMachineArn=state_machine_arn, input=json.dumps(execution_vars))

    execution_arn = response["executionArn"]
    output = json.loads(
        _get_event_output(execution_arn=execution_arn, event_type="TaskSubmitted", event_id=10, details_key="output")
    )

    return {
        "ExecutionType": "eks",
        "ExecutionArn": execution_arn,
        "Identifier": output["ResponseBody"]["metadata"]["name"],
    }


def _start_eks_ec2(event: Dict[str, Any], execution_vars: Dict[str, Any]) -> Dict[str, str]:
    logger.info(f"start_eks_ec2: {json.dumps(execution_vars)}")

    state_machine_arn = os.environ["EKS_EC2_STATE_MACHINE_ARN"]
    response = sfn.start_execution(stateMachineArn=state_machine_arn, input=json.dumps(execution_vars))

    execution_arn = response["executionArn"]
    output = json.loads(
        _get_event_output(execution_arn=execution_arn, event_type="TaskSubmitted", event_id=10, details_key="output")
    )

    return {
        "ExecutionType": "eks",
        "ExecutionArn": execution_arn,
        "Identifier": output["ResponseBody"]["metadata"]["name"],
    }


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, str]:
    logger.info(f"Lambda metadata: {json.dumps(event)} (type = {type(event)})")

    task_type = event.get("task_type", None)
    compute = event.get("compute", {"compute_type": "eks", "node_type": "fargate"})
    tasks = event.get("tasks", None)
    jupyterhub_user = event.get("jupyterhub_user", None)

    if None in [task_type, tasks, jupyterhub_user]:
        raise ValueError(
            f"Invalid input: task_type ({task_type}), tasks ({tasks}), "
            f"and jupyterhub_user ({jupyterhub_user}) are required"
        )

    compute_type = compute.get("compute_type", "").lower()
    node_type = compute.get("node_type", "").lower()
    cluster_name = compute.get("cluster_name", os.environ["DEFAULT_EKS_CLUSTER"])
    cpu = compute.get("cpu", os.environ["DEFAULT_CPU"])
    memory = compute.get("memory", os.environ["DEFAULT_MEMORY"])

    execution_vars = {
        "ClusterName": cluster_name,
        "TaskType": task_type,
        "Tasks": json.dumps({"tasks": tasks}),
        "Compute": json.dumps({"compute": compute}),
        "JupyterHubUser": jupyterhub_user,
        "Timeout": event.get("timeout", 99999999),
        "EnvVars": event.get("env_vars", None),
        "CPU": f"{cpu}",
        "Memory": f"{memory}",
    }

    if compute_type == "ecs" and node_type == "fargate":
        return _start_ecs_fargate(event, execution_vars)
    elif compute_type == "ecs" and node_type == "ec2":
        return _start_ecs_ec2(event, execution_vars)
    elif compute_type == "eks" and node_type == "fargate":
        return _start_eks_fargate(event, execution_vars)
    elif compute_type == "eks" and node_type == "ec2":
        return _start_eks_ec2(event, execution_vars)
    else:
        raise ValueError(f"Invalid compute_type: '{compute_type}' or node_type: '{node_type}'")
