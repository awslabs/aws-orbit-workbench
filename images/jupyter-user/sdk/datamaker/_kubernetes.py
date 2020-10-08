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
from typing import Any, Dict, List

from kubernetes.client import (
    V1beta1CronJob,
    V1beta1CronJobSpec,
    V1beta1CronJobStatus,
    V1beta1JobTemplateSpec,
    V1Container,
    V1EnvVar,
    V1JobSpec,
    V1ObjectMeta,
    V1PersistentVolumeClaimVolumeSource,
    V1PodSpec,
    V1PodTemplateSpec,
    V1ResourceRequirements,
    V1Volume,
    V1VolumeMount,
)

TEAM = os.environ.get("TEAM", "NO_TEAM_CONFIGURED")
ACCOUNT_ID = os.environ.get("ACCOUNT_ID", "NO_ACCOUNT_ID_CONFIGURED")
REGION = os.environ.get("AWS_DEFAULT_REGION", "NO_REGION_CONFIGURED")
IMAGE = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/datamaker-jupyter-user:latest"


def _job_template_spec(name: str, cmds: List[str], env_vars: Dict[str, Any]) -> V1beta1JobTemplateSpec:
    return V1beta1JobTemplateSpec(
        spec=V1JobSpec(
            backoff_limit=0,
            template=V1PodTemplateSpec(
                spec=V1PodSpec(
                    containers=[
                        V1Container(
                            name=name,
                            image=IMAGE,
                            command=cmds,
                            env=[V1EnvVar(name=k, value=v) for k, v in env_vars.items()],
                            volume_mounts=[V1VolumeMount(name="efs-volume", mount_path="/efs")],
                            resources=V1ResourceRequirements(
                                limits={"cpu": 1, "memory": "2G"}, requests={"cpu": 1, "memory": "2G"}
                            ),
                        )
                    ],
                    restart_policy="Never",
                    node_selector={"team": TEAM},
                    volumes=[
                        V1Volume(
                            name="efs-volume",
                            persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(claim_name="jupyterhub"),
                        )
                    ],
                )
            ),
        )
    )


def _cron_job(name: str, namespace: str, schedule: str, cmds: List[str], env_vars: Dict[str, Any]) -> V1beta1CronJob:
    return V1beta1CronJob(
        api_version="batch/v1beta1",
        kind="CronJob",
        metadata=V1ObjectMeta(namespace=namespace, name=name),
        status=V1beta1CronJobStatus(),
        spec=V1beta1CronJobSpec(
            schedule=schedule, job_template=_job_template_spec(name=name, cmds=cmds, env_vars=env_vars)
        ),
    )
