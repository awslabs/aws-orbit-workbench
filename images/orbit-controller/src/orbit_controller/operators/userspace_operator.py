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
from typing import Any, Dict, Optional

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
    settings.persistence.finalizer = "userspace-operator.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))


def _should_index_podsetting(labels: kopf.Labels, **_: Any) -> bool:
    return labels.get("orbit/space") == "team" and "orbit/team" in labels and "orbit/disable-watcher" not in labels


@kopf.index(ORBIT_API_GROUP, ORBIT_API_VERSION, "podsettings", when=_should_index_podsetting)  # type: ignore
def podsettings_idx(
    namespace: str, name: str, labels: kopf.Labels, spec: kopf.Spec, **_: Any
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Index of podsettings by team"""
    return {
        labels["orbit/team"]: {
            "namespace": namespace,
            "name": name,
            "labels": labels,
            "spec": spec,
        }
    }


@kopf.on.resume(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "userspaces",
    field="status.installation.installationStatus",
    value=kopf.ABSENT,
)
@kopf.on.create(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "userspaces",
    field="status.installation.installationStatus",
    value=kopf.ABSENT,
)
def install_team(patch: kopf.Patch, **_: Any) -> str:
    patch["status"] = {"installation": {"installationStatus": "Installed"}}
    return "Installed"


@kopf.on.delete(ORBIT_API_GROUP, ORBIT_API_VERSION, "userspaces")
def uninstall_team(**_: Any) -> str:
    return "Uninstalled"


