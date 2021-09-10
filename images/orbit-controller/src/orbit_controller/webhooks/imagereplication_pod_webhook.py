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
from typing import Any, Dict, List

import kopf
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dynamic_client
from orbit_controller.utils import imagereplication_utils

CONFIG: Dict[str, Any]


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
    settings.persistence.finalizer = "imagereplication-pod-webhook.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))

    global CONFIG
    CONFIG = imagereplication_utils.get_config()
    logger.info("CONFIG: %s", CONFIG)


def _check_replication_status(value: str, **_: Any) -> bool:
    return value not in ["Failed", "MaxAttemptsExceeded"]


@kopf.index(  # type: ignore
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "imagereplications",
    field="status.replication.replicationStatus",
    value=_check_replication_status,
)
def imagereplications_idx(namespace: str, name: str, spec: kopf.Spec, status: kopf.Status, **_: Any) -> Dict[str, Any]:
    replication_status = status.get("replication", {}).get("replicationStatus", None)
    return {
        spec["destination"]: {
            "namespace": namespace,
            "name": name,
            "source": spec["source"],
            "replicationStatus": replication_status,
        }
    }


@kopf.on.mutate("pods", id="update-pod-images")  # type: ignore
def update_pod_images(
    spec: kopf.Spec,
    patch: kopf.Patch,
    dryrun: bool,
    logger: kopf.Logger,
    imagereplications_idx: kopf.Index[str, str],
    **_: Any,
) -> kopf.Patch:
    if dryrun:
        logger.debug("DryRun - Skip Pod Mutation")
        return patch

    annotations = {}
    init_containers: List[Dict[str, Any]] = []
    containers: List[Dict[str, Any]] = []
    replications = {}

    def process_containers(src_containers: List[Dict[str, Any]], dest_containers: List[Dict[str, Any]]) -> None:
        for container in src_containers:
            image = container.get("image", "")
            desired_image = imagereplication_utils.get_desired_image(image=image, config=CONFIG)
            if image != desired_image:
                container_copy = deepcopy(container)
                container_copy["image"] = desired_image
                dest_containers.append(container_copy)
                replications[image] = desired_image
                annotations[f"original-container-image~1{container['name']}"] = image

    process_containers(spec.get("initContainers", []), init_containers)
    process_containers(spec.get("containers", []), containers)

    if replications:
        client = dynamic_client()
        for source, destination in replications.items():
            if not imagereplications_idx.get(destination, []):
                imagereplication_utils.create_imagereplication(
                    namespace="orbit-system", source=source, destination=destination, client=client, logger=logger
                )
            else:
                logger.debug("Skipping ImageReplication Creation")

    if annotations:
        patch["metadata"] = {"annotations": annotations}
        patch["spec"] = {}
    if init_containers:
        patch["spec"]["initContainers"] = init_containers
    if containers:
        patch["spec"]["containers"] = containers

    logger.debug("Patch: %s", str(patch))
    return patch
