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
from typing import Any, Dict

import kopf
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dynamic_client
from orbit_controller.utils import poddefault_utils


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, logger: kopf.Logger, **_: Any) -> None:
    settings.persistence.progress_storage = kopf.MultiProgressStorage(
        [
            kopf.AnnotationsProgressStorage(prefix="orbit.aws"),
            kopf.StatusProgressStorage(field="status.orbit-aws"),
        ]
    )
    settings.persistence.finalizer = "podsetting-operator.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))


def _should_index_namespaces(labels: Dict[str, str], **_: Any) -> bool:
    return labels.get("orbit/space", None) == "user" and "orbit/team" in labels


@kopf.index("namespaces", when=_should_index_namespaces)  # type: ignore
def namespaces_idx(
    name: str, annotations: Dict[str, str], labels: Dict[str, str], **_: Any
) -> Dict[str, Dict[str, Any]]:
    """Index of user namespaces by team"""
    return {
        labels["orbit/teams"]: {
            "name": name,
            "annotations": annotations,
            "labels": labels,
        }
    }


def _should_process_podsetting(labels: Dict[str, str], status: kopf.Status, **_: Any) -> bool:
    return (
        labels.get("orbit/space") == "team"
        and "orbit/disable-watcher" not in labels
        and "podDefaultsCreation" not in status
    )


@kopf.on.resume(ORBIT_API_GROUP, ORBIT_API_VERSION, "podsettings", when=_should_process_podsetting)  # type: ignore
@kopf.on.create(ORBIT_API_GROUP, ORBIT_API_VERSION, "podsettings", when=_should_process_podsetting)  # type: ignore
def create_poddefaults(
    namespace: str,
    name: str,
    labels: Dict[str, str],
    spec: kopf.Spec,
    status: kopf.Status,
    patch: kopf.Patch,
    logger: kopf.Logger,
    namespaces_idx: kopf.Index[str, Dict[str, Any]],
    **_: Any,
) -> str:
    team = labels.get("orbit/team", None)
    if team is None:
        logger.error("Missing required orbit/team label")
        patch["status"] = {"podDefaultsCreation": "MissingTeam"}
        return "MissingTeam"

    # Contruct a pseudo poddefault for the team to be copied to users
    poddefault = poddefault_utils.construct(
        name=name,
        desc=spec.get("desc", ""),
        labels={"orbit/space": "team", "orbit/team": team},
    )
    user_namespaces = [ns.get("name") for ns in namespaces_idx.get(team, [])]
    poddefault_utils.copy_poddefaults_to_user_namespaces(
        poddefaults=[poddefault],
        user_namespaces=user_namespaces,
        client=dynamic_client(),
        logger=logger,
    )

    patch["status"] = {"podDefaultsCreation": "Complete"}
    return "PodDefaultsCreated"


@kopf.on.update(ORBIT_API_GROUP, ORBIT_API_VERSION, "podsettings", when=_should_process_podsetting)  # type: ignore
def update_poddefaults(
    namespace: str,
    name: str,
    labels: Dict[str, str],
    spec: kopf.Spec,
    logger: kopf.Logger,
    namespaces_idx: kopf.Index[str, Dict[str, Any]],
    **_: Any,
) -> str:
    team = labels.get("orbit/team", None)
    if team is None:
        logger.error("Missing required orbit/team label")
        return "MissingTeam"

    # Contruct a pseudo poddefault for the team to be copied to users
    poddefault = poddefault_utils.construct(
        name=name,
        desc=spec.get("desc", ""),
        labels={"orbit/space": "team", "orbit/team": team},
    )
    user_namespaces = [namespace["name"] for namespace in namespaces_idx.get(team, [])]
    poddefault_utils.modify_poddefaults_in_user_namespaces(
        poddefaults=[poddefault],
        user_namespaces=user_namespaces,
        client=dynamic_client(),
        logger=logger,
    )

    return "PodDefaultsUpdated"


@kopf.on.delete(ORBIT_API_GROUP, ORBIT_API_VERSION, "podsettings", when=_should_process_podsetting)  # type: ignore
def delete_poddefaults(
    namespace: str,
    name: str,
    labels: Dict[str, str],
    spec: kopf.Spec,
    logger: kopf.Logger,
    namespaces_idx: kopf.Index[str, Dict[str, Any]],
    **_: Any,
) -> str:
    team = labels.get("orbit/team", None)
    if team is None:
        logger.error("Missing required orbit/team label")
        return "MissingTeam"

    # Contruct a pseudo poddefault for the team to be deleted from users
    poddefault = poddefault_utils.construct(
        name=name,
        desc=spec.get("desc", ""),
        labels={"orbit/space": "team", "orbit/team": team},
    )
    user_namespaces = [namespace["name"] for namespace in namespaces_idx.get(team, [])]
    poddefault_utils.delete_poddefaults_from_user_namespaces(
        poddefaults=[poddefault],
        user_namespaces=user_namespaces,
        client=dynamic_client(),
        logger=logger,
    )

    return "PodDefaultsDeleted"
