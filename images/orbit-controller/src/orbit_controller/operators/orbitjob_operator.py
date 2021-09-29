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
from typing import Any, Dict, Optional, Tuple, cast

import boto3
import botocore
import kopf
from kubernetes.client import BatchV1Api, V1Job, V1ObjectMeta
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION
from orbit_controller.utils import job_utils

ENV_CONTEXT: Optional[Dict[str, Any]] = None


def _get_parameter(client: boto3.client, name: str) -> Optional[Dict[str, Any]]:
    try:
        return cast(Dict[str, Any], json.loads(client.get_parameter(Name=name)["Parameter"]["Value"]))
    except botocore.errorfactory.ParameterNotFound:
        return None


def _load_env_context_from_ssm(env_name: str) -> Optional[Dict[str, Any]]:
    ssm = boto3.client("ssm")
    context_parameter_name: str = f"/orbit/{env_name}/context"
    return _get_parameter(ssm, name=context_parameter_name)


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, logger: kopf.Logger, **_: Any) -> None:
    settings.persistence.progress_storage = kopf.MultiProgressStorage(
        [
            kopf.AnnotationsProgressStorage(prefix="orbit.aws"),
            kopf.StatusProgressStorage(field="status.orbit-aws"),
        ]
    )
    settings.persistence.finalizer = "orbitjob-operator.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))


def _should_index_jobs(meta: kopf.Meta, **_: Any) -> bool:
    for owner_reference in meta.get("ownerReferences", []):
        if owner_reference.get("kind") == "OrbitJob":
            return True
    else:
        return False


@kopf.index("jobs", when=_should_index_jobs)  # type: ignore
def jobs_idx(
    namespace: str, logger: kopf.Logger, name: str, meta: kopf.Meta, status: kopf.Status, **_: Any
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Index of k8s jobs by orbitjob namespace/name"""

    orbit_job_reference = [owner_reference for owner_reference in meta.get("ownerReferences", [{}])].pop()
    return {(namespace, orbit_job_reference.get("name")): {"namespace": namespace, "name": name, "status": status}}


def _check_existence_k8s_job(
    namespace: str,
    name: str,
    jobs_idx: kopf.Index[Tuple[str, str], Dict[str, Any]],
    **_: Any,
) -> bool:
    k8s_job: Optional[Dict[str, Any]] = None
    for k8s_job in jobs_idx.get((namespace, name), []):
        if k8s_job is not None:
            return True
    else:
        return False


@kopf.index("namespaces")  # type: ignore
def namespaces_idx(name: str, logger: kopf.Logger, labels: kopf.Labels, **_: Any) -> Dict[str, Any]:
    """Index of namespace by name"""

    return {name: {"name": name, "team": labels.get("orbit/team"), "env": labels.get("orbit/env")}}


@kopf.index(ORBIT_API_GROUP, ORBIT_API_VERSION, "podsettings")  # type: ignore
def podsettings_idx(
    namespace: str, name: str, labels: kopf.Labels, spec: kopf.Spec, **_: Any
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Index of podsettings by namespace (team)/name"""
    return {
        (namespace, name): {"namespace": namespace, "name": name, "labels": labels, "image": spec.get("image", None)}
    }


def _should_process_orbitjob(status: kopf.Status, **_: Any) -> bool:
    return "orbitJobOperator" not in status or "jobStatus" not in status["orbitJobOperator"]


@kopf.on.resume(ORBIT_API_GROUP, ORBIT_API_VERSION, "orbitjobs", when=_should_process_orbitjob)  # type: ignore
@kopf.on.create(ORBIT_API_GROUP, ORBIT_API_VERSION, "orbitjobs", when=_should_process_orbitjob)
def create_job(
    namespace: str,
    name: str,
    labels: kopf.Labels,
    annotations: kopf.Annotations,
    spec: kopf.Spec,
    status: kopf.Status,
    patch: kopf.Patch,
    logger: kopf.Logger,
    namespaces_idx: kopf.Index[str, Dict[str, Any]],
    podsettings_idx: kopf.Index[Tuple[str, str], Dict[str, Any]],
    **_: Any,
) -> str:
    ns: Optional[Dict[str, Any]] = None
    for ns in namespaces_idx.get(namespace, []):
        logger.debug("ns: %s", ns)

    if ns is None:
        patch["status"] = {
            "orbitJobOperator": {"jobStatus": "JobCreationFailed", "error": "No Namespace resource found"}
        }
        return "JobCreationFailed"

    env = ns["env"]
    team = ns["team"]

    global ENV_CONTEXT  # Caching
    if ENV_CONTEXT is None:
        context = _load_env_context_from_ssm(env)
        if context is None:
            patch["status"] = {
                "orbitJobOperator": {"jobStatus": "JobCreationFailed", "error": "Unable to load Env Context from SSM"}
            }
            return "JobCreationFailed"
        else:
            ENV_CONTEXT = context

    node_type = spec.get("compute", {}).get("nodeType", "fargate")
    labels = {
        "app": "orbit-runner",
        "orbit/node-type": node_type,
        "notebook-name": spec.get("notebookName", ""),
        "orbit/attach-security-group": "yes" if node_type == "ec2" else "no",
    }

    podsetting_metadata: Dict[str, Any] = {}
    for podsetting_metadata in podsettings_idx.get((team, spec.get("compute", {}).get("podSetting", None)), []):
        logger.debug("PodSetting: %s", podsetting_metadata)

    job_spec = job_utils.construct_job_spec(
        env=env,
        team=team,
        env_context=ENV_CONTEXT,
        podsetting_metadata=podsetting_metadata,
        orbit_job_spec=spec,
        labels=labels,
    )
    job = V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=V1ObjectMeta(labels={**labels, **spec.get("compute", {}).get("labels", {})}),
        spec=job_spec,
    )

    kopf.adopt(job, nested="spec.template")
    job_instance: V1Job = BatchV1Api().create_namespaced_job(namespace=namespace, body=job)

    job_instance_metadata: V1ObjectMeta = job_instance.metadata
    logger.debug("Started Job: %s", job_instance_metadata.name)

    patch["status"] = {
        "orbitJobOperator": {"jobStatus": "JobCreated", "jobName": job_instance_metadata.name, "nodeType": node_type}
    }
    return "JobCreated"


@kopf.on.timer(  # type: ignore
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "orbitjobs",
    interval=5,
    initial_delay=20,
    when=_check_existence_k8s_job,  # type: ignore
)
def orbit_job_monitor(
    namespace: str,
    name: str,
    patch: kopf.Patch,
    logger: kopf.Logger,
    namespaces_idx: kopf.Index[str, Dict[str, Any]],
    jobs_idx: kopf.Index[Tuple[str, str], Dict[str, Any]],
    **_: Any,
) -> Any:
    ns: Optional[Dict[str, Any]] = None
    k8s_job: Optional[Dict[str, Any]] = None

    for ns in namespaces_idx.get(namespace, []):
        logger.debug("ns: %s", ns)

    if ns is None:
        patch["status"] = {
            "orbitJobOperator": {"jobStatus": "JobDetailsNotFound", "error": "No Namespace resource found"}
        }
        return "JobDetailsNotFound"

    for k8s_job in jobs_idx.get((namespace, name), []):
        logger.debug("k8s_job: %s", k8s_job)

    if k8s_job is None:  # To tackle the race condition caused by Timer
        return "JobMetadataNotFound"

    job_status = k8s_job.get("status", {}).get("conditions", [{}])[0].get("type")
    k8s_job_reason = k8s_job.get("status", {}).get("conditions", [{}])[0].get("status")
    k8s_job_message = k8s_job.get("status", {}).get("conditions", [{}])[0].get("message")

    patch["status"] = {
        "orbitJobOperator": {
            "jobStatus": job_status,
            "jobName": k8s_job.get("name"),
            "k8sJobReason": k8s_job_reason,
            "k8sJobMessage": k8s_job_message,
        }
    }
    return job_status
