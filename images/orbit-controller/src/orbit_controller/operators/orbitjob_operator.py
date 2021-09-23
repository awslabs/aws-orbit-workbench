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
import os
from typing import Any, Dict, Tuple

import kopf
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION


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
def jobs_idx(name: str, namespace: str, meta: kopf.Meta, spec: kopf.Spec, **_: Any) -> Dict[Tuple[str, str], kopf.Spec]:
    
    return {
        (namespace, name): spec
    }


def _should_process_orbitjob(status: kopf.Status, **_: Any) -> bool:
    return "orbitJobOperator" not in status or "jobStatus" not in status["orbitJobOperator"]


@kopf.on.resume(ORBIT_API_GROUP, ORBIT_API_VERSION, "orbitjobs", when=_should_process_orbitjob)  # type: ignore
@kopf.on.create(ORBIT_API_GROUP, ORBIT_API_VERSION, "orbitjobs", when=_should_process_orbitjob)  # type: ignore
def create_job(namespace: str, name: str, labels: Dict[str, str], annotations: Dict[str, str], spec: kopf.Spec, status: kopf.Status, patch: kopf.Patch, **_: Any) -> str:
    patch["status"] = {"orbitJobOperator": {"jobStatus": "JobCreated"}}
    return "JobCreated"