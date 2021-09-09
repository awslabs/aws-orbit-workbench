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
from copy import deepcopy
from typing import Any, Dict, List, Optional, cast

import kopf
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION
from orbit_controller.utils import podsetting_utils


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, logger: kopf.Logger, **_: Any) -> None:
    settings.admission.server = kopf.WebhookServer(
        cafile="/certs/ca.crt", certfile="/certs/tls.crt", pkeyfile="/certs/tls.key", port=443
    )
    settings.persistence.progress_storage = kopf.MultiProgressStorage(
        [
            kopf.AnnotationsProgressStorage(prefix="orbit.aws"),
            kopf.StatusProgressStorage(field="status.orbit-aws"),
        ]
    )
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))


@kopf.index("namespaces")  # type: ignore
def namespaces_idx(
    name: str, annotations: Dict[str, str], labels: Dict[str, str], **_: Any
) -> Dict[str, Dict[str, Any]]:
    """Index of namespaces by name"""
    return {name: {"name": name, "annotations": annotations, "labels": labels}}


def _should_index_podsetting(labels: Dict[str, str], **_: Any) -> bool:
    return labels.get("orbit/space") == "team" and "orbit/team" in labels


@kopf.index(ORBIT_API_GROUP, ORBIT_API_VERSION, "podsettings", when=_should_index_podsetting)  # type: ignore
def podsettings_idx(
    namespace: str, name: str, labels: Dict[str, str], spec: kopf.Spec, **_: Any
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Index of podsettings by team"""
    return {labels["orbit/team"]: {"namespace": namespace, "name": name, "labels": labels, "spec": spec}}


@kopf.on.mutate("pods", id="apply-pod-settings")  # type: ignore
def update_pod_images(
    namespace: str,
    labels: Dict[str, str],
    body: kopf.Body,
    patch: kopf.Patch,
    dryrun: bool,
    logger: kopf.Logger,
    warnings: List[str],
    namespaces_idx: kopf.Index[str, Dict[str, Any]],
    podsettings_idx: kopf.Index[str, Dict[str, Any]],
    **_: Any,
) -> kopf.Patch:
    if dryrun:
        logger.debug("DryRun - Skip Pod Mutation")
        return patch

    ns = cast(List[Dict[str, Any]], namespaces_idx.get(namespace, [{}]))[0]

    team = ns.get("labels", {}).get("orbit/team", None)
    if not team:
        logger.info("No 'orbit/team' label found on Pod's Namespace: %s", namespace)
        # warnings.append(f"No 'orbit/team' label found on Pod's Namespace: {namespace}")
        return patch

    team_podsettings: List[Dict[str, Any]] = cast(List[Dict[str, Any]], podsettings_idx.get(team, []))
    if not team_podsettings:
        logger.info("No PodSettings found for Pod's Team: %s", team)
        # warnings.append(f"No PodSettings found for Pod's Team: {team}")
        return patch

    fitlered_podsettings = podsetting_utils.filter_podsettings(
        podsettings=team_podsettings, pod_labels=labels, logger=logger
    )
    if not fitlered_podsettings:
        logger.info("No PodSetting Selectors matched the Pod")
        return patch

    applied_podsetting_names = []
    modified_body = deepcopy(body)
    for podsetting in fitlered_podsettings:
        try:
            podsetting_utils.apply_settings_to_pod(namespace=ns, podsetting=podsetting, pod=body, logger=logger)
            applied_podsetting_names.append(podsetting["name"])
        except Exception as e:
            logger.error("Error applying PodSetting %s: %s", podsetting["name"], str(e))
            warnings.append(f"Error applying PodSetting {podsetting['name']}: {str(e)}")

    if body == modified_body:
        logger.warn("PodSetting Selectors matched the Pod but no changes were applied")
        warnings.append("PodSetting Selectors matched the Pod but no changes were applied")
        return patch

    patch["metadata"] = {}
    patch["metadata"]["annotations"] = {
        **modified_body["metadata"].get("annotations", {}),
        **{"orbit/applied-podsettings": ",".join(applied_podsetting_names)},
    }
    if "labels" in modified_body["metadata"]:
        patch["metadata"]["labels"] = modified_body["meta"]
    patch["spec"] = modified_body["spec"]

    logger.info("Applying Patch %s", patch)
    return patch
