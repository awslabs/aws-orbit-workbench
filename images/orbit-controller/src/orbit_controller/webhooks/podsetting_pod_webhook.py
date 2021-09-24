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
        cafile="/certs/ca.crt",
        certfile="/certs/tls.crt",
        pkeyfile="/certs/tls.key",
        port=443,
    )
    settings.persistence.progress_storage = kopf.MultiProgressStorage(
        [
            kopf.AnnotationsProgressStorage(prefix="orbit.aws"),
            kopf.StatusProgressStorage(field="status.orbit-aws"),
        ]
    )
    settings.persistence.finalizer = "podsetting-pod-webhook.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))


@kopf.index("namespaces")  # type: ignore
def namespaces_idx(
    name: str, annotations: kopf.Annotations, labels: kopf.Labels, **_: Any
) -> Dict[str, Dict[str, Any]]:
    """Index of namespaces by name"""
    return {name: {"name": name, "annotations": annotations, "labels": labels}}


def _should_index_podsetting(labels: kopf.Labels, **_: Any) -> bool:
    return labels.get("orbit/space") == "team" and "orbit/team" in labels


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


@kopf.on.mutate("pods", id="apply-pod-settings")  # type: ignore
def update_pod_images(
    namespace: str,
    labels: kopf.Labels,
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

    # This is a hack to get the only namespace from the index Store
    ns: Dict[str, Any] = {}
    for ns in cast(List[Dict[str, Any]], namespaces_idx.get(namespace, [{}])):
        logger.debug("Namespace: %s", ns)

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
    body_dict = {
        "metadata": {k: v for k, v in body["metadata"].items()},
        "spec": {k: v for k, v in body["spec"].items()},
    }
    logger.debug("BodyDict: %s", body_dict)
    mutable_body = deepcopy(body)
    for podsetting in fitlered_podsettings:
        try:
            podsetting_utils.apply_settings_to_pod(namespace=ns, podsetting=podsetting, pod=mutable_body, logger=logger)
            applied_podsetting_names.append(podsetting["name"])
        except Exception as e:
            logger.exception("Error applying PodSetting %s: %s", podsetting["name"], str(e))
            warnings.append(f"Error applying PodSetting {podsetting['name']}: {str(e)}")

    if body_dict["spec"] == mutable_body["spec"] and body_dict["metadata"] == mutable_body["metadata"]:
        logger.warn("PodSetting Selectors matched the Pod but no changes were applied")
        warnings.append("PodSetting Selectors matched the Pod but no changes were applied")
        return patch

    patch["metadata"] = {}
    patch["metadata"]["annotations"] = {
        **mutable_body["metadata"].get("annotations", {}),
        **{"orbit/applied-podsettings": ",".join(applied_podsetting_names)},
    }
    patch["metadata"]["annotations"] = {k.replace("/", "~1"): v for k, v in patch["metadata"]["annotations"].items()}

    if "labels" in mutable_body["metadata"]:
        patch["metadata"]["labels"] = {k.replace("/", "~1"): v for k, v in mutable_body["metadata"]["labels"].items()}

    patch["spec"] = mutable_body["spec"]

    logger.info("Applying Patch %s", patch)
    return patch
