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
import os
from typing import Any, Dict, List, Optional

import kopf
from kubernetes.client import (
    V1Container,
    V1ContainerPort,
    V1EnvVar,
    V1JobSpec,
    V1ObjectMeta,
    V1Pod,
    V1PodSecurityContext,
    V1PodSpec,
    V1ResourceRequirements,
    V1SecurityContext,
)


def _make_pod(
    name: Optional[str] = None,
    generate_name: Optional[str] = None,
    cmd: Optional[List[str]] = None,
    port: Optional[int] = None,
    image: Optional[str] = None,
    run_as_uid: Optional[int] = None,
    run_as_gid: Optional[int] = None,
    run_privileged: bool = False,
    allow_privilege_escalation: bool = True,
    env: Optional[Dict[str, str]] = None,
    labels: Optional[Dict[str, str]] = None,
    service_account: Optional[str] = None,
    priority_class_name: Optional[str] = None,
) -> V1Pod:
    pod = V1Pod()
    pod.kind = "Pod"
    pod.api_version = "v1"

    pod.metadata = V1ObjectMeta(name=name, generate_name=generate_name, labels=(labels or {}).copy())

    pod.spec = V1PodSpec(containers=[])
    pod.spec.restart_policy = "OnFailure"

    if priority_class_name:
        pod.spec.priority_class_name = priority_class_name

    pod_security_context = V1PodSecurityContext()
    # Only clutter pod spec with actual content
    if not all([e is None for e in pod_security_context.to_dict().values()]):
        pod.spec.security_context = pod_security_context

    container_security_context = V1SecurityContext()
    if run_as_uid is not None:
        container_security_context.run_as_user = int(run_as_uid)
    if run_as_gid is not None:
        container_security_context.run_as_group = int(run_as_gid)
    if run_privileged:
        container_security_context.privileged = True
    if not allow_privilege_escalation:
        container_security_context.allow_privilege_escalation = False
    # Only clutter container spec with actual content
    if all([e is None for e in container_security_context.to_dict().values()]):
        container_security_context = None

    prepared_env = []
    for k, v in (env or {}).items():
        prepared_env.append(V1EnvVar(name=k, value=v))
    notebook_container = V1Container(
        name="orbit-runner",
        image=image,
        ports=[V1ContainerPort(name="notebook-port", container_port=port)],
        env=prepared_env,
        args=cmd,
        resources=V1ResourceRequirements(),
        security_context=container_security_context,
    )

    if service_account is None:
        # This makes sure that we don't accidentally give access to the whole
        # kubernetes API to the users in the spawned pods.
        pod.spec.automount_service_account_token = False
    else:
        pod.spec.service_account_name = service_account

    notebook_container.resources.requests = {}
    notebook_container.resources.limits = {}

    pod.spec.containers.append(notebook_container)
    pod.spec.volumes = []

    if priority_class_name:
        pod.spec.priority_class_name = priority_class_name

    return pod


def construct_job_spec(
    env: str,
    team: str,
    env_context: Dict[str, Any],
    podsetting_metadata: Dict[str, Any],
    orbit_job_spec: kopf.Spec,
    labels: kopf.Labels,
) -> V1JobSpec:
    compute = orbit_job_spec.get("compute", {"computeType": "eks", "nodeType": "fargate"})

    # Convert all the compute parameters to their SDK equivalents until we fix the SDK
    # and python-utils
    converted_compute = {}
    if "computeType" in compute:
        converted_compute["compute_type"] = compute["computeType"]
    if "nodeType" in compute:
        converted_compute["node_type"] = compute["nodeType"]
    if "env" in compute:
        converted_compute["env_vars"] = compute["env"]
    if "snsTopicName" in compute:
        converted_compute["sns.topic.name"] = compute["snsTopicName"]
    if "priorityClassName" in compute:
        converted_compute["priorityClassName"] = compute["priorityClassName"]
    if "podSetting" in compute:
        converted_compute["podsetting"] = compute["podSetting"]
    if "labels" in compute:
        converted_compute["labels"] = compute["labels"]
    if "container" in compute:
        if "concurrentProcesses" in compute["container"]:
            converted_compute["container"] = {"p_concurrent": compute["container"]["concurrentProcesses"]}

    pod_labels = {
        **labels,
        **orbit_job_spec.get("compute", {}).get("labels", {}),
    }
    pod_labels["app"] = "orbit-runner"
    pod_labels[f"orbit/{podsetting_metadata.get('name', None)}"] = ""

    pod_env = {
        "task_type": orbit_job_spec["taskType"],
        "tasks": json.dumps({"tasks": orbit_job_spec["tasks"]}),
        "compute": json.dumps({"compute": converted_compute}),
        "AWS_ORBIT_ENV": env,
        "AWS_ORBIT_TEAM_SPACE": team,
    }
    pod_image = (
        podsetting_metadata["image"]
        if podsetting_metadata["image"] is not None
        else (
            f"{env_context['Images']['JupyterUser']['Repository']}:"
            f"{env_context['Images']['JupyterUser']['Version']}"
        )
    )

    pod_params = {
        # "name": f"run-{orbit_job_spec['taskType']}",
        "cmd": ["bash", "-c", "python /opt/python-utils/notebook_cli.py"],
        "port": 22,
        "image": pod_image,
        "service_account": "default-editor",
        "run_privileged": False,
        "allow_privilege_escalation": True,
        "env": pod_env,
        "priority_class_name": orbit_job_spec.get("priorityClassName"),
        "labels": pod_labels,
        "run_as_uid": 1000,
        "run_as_gid": 100,
    }

    pod = _make_pod(**pod_params)
    pod.spec.restart_policy = "Never"
    return V1JobSpec(
        backoff_limit=0, template=pod, ttl_seconds_after_finished=int(os.environ.get("TTL_SECONDS_AFTER_FINISHED", 120))
    )
