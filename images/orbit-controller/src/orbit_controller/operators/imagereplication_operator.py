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
import threading
import time
from queue import Queue
from typing import Any, Dict, Union, cast

import boto3
import kopf
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dynamic_client
from orbit_controller.utils import imagereplication_utils

LOCK: threading.Lock
CONFIG: Dict[str, Any]
WORKERS_IN_PROCESS: int = 0


def _set_globals(logger: Union[kopf.Logger, logging.Logger]) -> None:
    global LOCK
    LOCK = threading.Lock()

    global CONFIG
    CONFIG = imagereplication_utils.get_config()
    logger.info("CONFIG: %s", CONFIG)

    global WORKERS_IN_PROCESS
    WORKERS_IN_PROCESS = 0


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, logger: kopf.Logger, **_: Any) -> None:
    settings.persistence.progress_storage = kopf.MultiProgressStorage(
        [
            kopf.AnnotationsProgressStorage(prefix="orbit.aws"),
            kopf.StatusProgressStorage(field="status.orbit-aws"),
        ]
    )
    settings.persistence.finalizer = "imagereplication-operator.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))
    _set_globals(logger=logger)


@kopf.on.resume(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "imagereplications",
    field="status.replication",
    value=kopf.ABSENT,
)
@kopf.on.create(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "imagereplications",
    field="status.replication",
    value=kopf.ABSENT,
)
def replication_checker(
    spec: kopf.Spec,
    status: kopf.Status,
    patch: kopf.Patch,
    logger: kopf.Logger,
    **_: Any,
) -> str:
    if status.get("replication", None) is not None:
        return cast(str, status["replication"].get("replicationStatus", "Unknown"))

    replication = {}
    if imagereplication_utils.image_replicated(image=spec["destination"], logger=logger):
        logger.info("Skipped: Image previously replicated to ECR")
        replication["replicationStatus"] = "ECRImageExists"
    else:
        logger.info("Starting Replication")
        replication["replicationStatus"] = "Pending"

    patch["status"] = {"replication": replication}
    return replication["replicationStatus"]


@kopf.timer(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "imagereplications",
    interval=5,
    field="status.replication.replicationStatus",
    value="Pending",
)
def scheduler(status: kopf.Status, patch: kopf.Patch, logger: kopf.Logger, **_: Any) -> str:
    replication = status.get("replication", {})
    replication["codeBuildStatus"] = None
    replication["codeBuildPhase"] = None
    replication["codeBuildId"] = None

    attempt = replication.get("attempt", 0) + 1
    if attempt > CONFIG["max_replication_attempts"]:
        replication["replicationStatus"] = "MaxAttemptsExceeded"
        replication["attempt"] = attempt

        patch["status"] = {"replication": replication}
    else:
        with LOCK:
            global WORKERS_IN_PROCESS
            logger.debug("WORKERS_IN_PROCESS: %s", WORKERS_IN_PROCESS)
            if WORKERS_IN_PROCESS < CONFIG["workers"]:
                WORKERS_IN_PROCESS += 1
                replication["replicationStatus"] = "Scheduled"
                replication["attempt"] = attempt

                patch["status"] = {"replication": replication}
                logger.info("Schedule Attempt: %s", replication["attempt"])

    return cast(str, replication["replicationStatus"])


def _needs_rescheduling(status: kopf.Status, **_: Any) -> bool:
    replication = status.get("replication", None)
    if replication:
        replication_status = replication.get("replicationStatus", None)
        attempt = replication.get("attempt", 0)
        return cast(
            bool,
            replication_status == "Failed" and attempt <= CONFIG["max_replication_attempts"],
        )
    else:
        return False


@kopf.timer(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "imagereplications",
    interval=5,
    when=_needs_rescheduling,
)
def rescheduler(status: kopf.Status, patch: kopf.Patch, logger: kopf.Logger, **_: Any) -> str:
    logger.debug("Rescheduling")
    replication = status.get("replication", {})
    failure_delay = replication.get("failureDelay", 0)

    if failure_delay > 0:
        replication["failureDelay"] = failure_delay - 5
    else:
        replication["replicationStatus"] = "Pending"
        replication["failureDelay"] = None

    patch["status"] = {"replication": replication}
    return "Rescheduled"


@kopf.on.timer(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "imagereplications",
    interval=5,
    field="status.replication.replicationStatus",
    value="Scheduled",
)
def codebuild_runner(
    spec: kopf.Spec,
    patch: kopf.Patch,
    status: kopf.Status,
    logger: kopf.Logger,
    **_: Any,
) -> str:
    replication = status.get("replication", {})

    build_id, error = imagereplication_utils.replicate_image(
        src=spec["source"], dest=spec["destination"], config=CONFIG
    )

    replication["replicationStatus"] = "Replicating"
    replication["codeBuildId"] = build_id

    if error:
        replication["replicationStatus"] = "Failed"
        replication["failureDelay"] = 30
        with LOCK:
            global WORKERS_IN_PROCESS
            WORKERS_IN_PROCESS -= 1

    patch["status"] = {"replication": replication}
    if error:
        logger.error("CodeBuildId: %s Error: %s", build_id, error)
    else:
        logger.info("CodeBuildId: %s Error: %s", build_id, error)

    return cast(str, replication["replicationStatus"])


@kopf.on.timer(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "imagereplications",
    interval=20,
    field="status.replication.replicationStatus",
    value="Replicating",
)
def codebuild_monitor(status: kopf.Status, patch: kopf.Patch, logger: kopf.Logger, **_: Any) -> str:
    replication = status.get("replication", {})

    build_id = replication.get("codeBuildId", None)

    client = boto3.client("codebuild")
    build = client.batch_get_builds(ids=[build_id])["builds"][0]
    replication["codeBuildStatus"] = build["buildStatus"]
    replication["codeBuildPhase"] = build["currentPhase"]

    if replication["codeBuildStatus"] not in "IN_PROGRESS":
        logger.info("CodeBuildId: %s BuildStatus: %s", build_id, replication["codeBuildStatus"])
        with LOCK:
            global WORKERS_IN_PROCESS
            WORKERS_IN_PROCESS -= 1
        codebuild_attempts = replication.get("codeBuildAttempts", [])
        codebuild_attempts.append(
            {
                "codeBuildId": build_id,
                "codeBuildStatus": build["buildStatus"],
                "codeBuildPhase": build["currentPhase"],
            }
        )
        replication["codeBuildAttempts"] = codebuild_attempts
        replication["replicationStatus"] = "Complete" if build["buildStatus"] == "SUCCEEDED" else "Failed"

    if replication["replicationStatus"] == "Failed":
        replication["failureDelay"] = 30

    patch["status"] = {"replication": replication}
    return cast(str, replication["codeBuildStatus"])


def replication_worker(queue: Queue, statuses: Dict[str, Any], logger: logging.Logger) -> None:  # type: ignore
    client = dynamic_client()

    while True:
        destination = queue.get(block=True, timeout=None)
        with LOCK:
            source = statuses.get(destination, {}).get("source", None)
            status = statuses.get(destination, {}).get("status", None)

        patch: Dict[str, Any] = {}
        spec = {"source": source, "destination": destination}

        if status is None:
            replication_status = replication_checker(status={}, spec=spec, patch=patch, logger=logger)  # type: ignore
            if replication_status == "ECRImageExists":
                logger.info("ECR Image already exists: %s", destination)
                queue.task_done()
                continue
            status = patch
            namespace, name = imagereplication_utils.create_imagereplication(
                namespace="orbit-system",
                source=source,
                destination=destination,
                client=client,
                logger=logger,
            )
            statuses[destination]["namespace"] = namespace
            statuses[destination]["name"] = name
            logger.debug("New Status: %s", status)
        else:
            replication_status = status.get("status", {}).get("replication", {}).get("replicationStatus", None)

        status = {**status, **patch}
        imagereplication_utils.update_imagereplication_status(
            namespace=statuses[destination]["namespace"],
            name=statuses[destination]["name"],
            status=status["status"],
            client=client,
            logger=logger,
        )
        logger.info("Replication Checker: %s Source: %s", replication_status, source)
        if replication_status not in ["Pending", "Failed"]:
            with LOCK:
                statuses[destination]["status"] = status
            queue.task_done()
            continue

        patch = {}
        replication_status = scheduler(status=status["status"], patch=patch, logger=logger)  # type: ignore
        status = {**status, **patch}
        imagereplication_utils.update_imagereplication_status(
            namespace=statuses[destination]["namespace"],
            name=statuses[destination]["name"],
            status=status["status"],
            client=client,
            logger=logger,
        )
        logger.info("Scheduler: %s Source: %s", replication_status, source)
        if replication_status != "Scheduled":
            with LOCK:
                statuses[destination]["status"] = status
            queue.task_done()
            continue

        patch = {}
        replication_status = codebuild_runner(  # type: ignore
            spec=cast(kopf.Spec, spec),
            status=status["status"],
            patch=cast(kopf.Patch, patch),
            logger=logger,
        )
        status = {**status, **patch}
        imagereplication_utils.update_imagereplication_status(
            namespace=statuses[destination]["namespace"],
            name=statuses[destination]["name"],
            status=status["status"],
            client=client,
            logger=logger,
        )
        logger.info("CodeBuild Runner: %s Source: %s", replication_status, source)
        if replication_status != "Replicating":
            if _needs_rescheduling(status=cast(kopf.Status, patch)):
                queue.put(destination)

            with LOCK:
                statuses[destination]["status"] = status
            queue.task_done()
            continue

        patch = {}
        replication_status = codebuild_monitor(status=status["status"], patch=patch, logger=logger)  # type: ignore
        status = {**status, **patch}
        imagereplication_utils.update_imagereplication_status(
            namespace=statuses[destination]["namespace"],
            name=statuses[destination]["name"],
            status=status["status"],
            client=client,
            logger=logger,
        )
        logger.info("CodeBuild Monitor: %s Source: %s", replication_status, source)
        while replication_status == "IN_PROGRESS":
            time.sleep(20)
            patch = {}
            replication_status = codebuild_monitor(status=status["status"], patch=patch, logger=logger)  # type: ignore
            status = {**status, **patch}

        logger.info("CodeBuild Monitor: %s Source: %s", replication_checker, source)
        if replication_status != "SUCCEEDED" and _needs_rescheduling(status=status["status"]):
            queue.put(destination)

        with LOCK:
            statuses[destination]["status"] = status
        imagereplication_utils.update_imagereplication_status(
            namespace=statuses[destination]["namespace"],
            name=statuses[destination]["name"],
            status=status["status"],
            client=client,
            logger=logger,
        )
        queue.task_done()
        continue


if __name__ == "__main__":
    from orbit_controller import logger

    _set_globals(logger=logger)

    statuses = {}
    queue = Queue()  # type: ignore

    logger.info("Priming work queue from inventory of known images")
    inventory_path = os.environ.get("INVENTORY_OVERRIDE", "/var/orbit-controller/image_inventory.txt")
    logger.info("Inventory Path: %s", inventory_path)
    with open(inventory_path, "r") as inventory:
        for source_image in inventory:
            source_image = source_image.strip()
            desired_image = imagereplication_utils.get_desired_image(image=source_image, config=CONFIG)
            if source_image != desired_image:
                logger.debug("Queueing: %s", desired_image)
                statuses[desired_image] = {
                    "source": source_image,
                    "destination": desired_image,
                    "status": None,
                }
                queue.put(desired_image)

    for i in range(CONFIG["workers"]):
        threading.Thread(
            target=replication_worker,
            daemon=True,
            name=f"Worker-{i}",
            kwargs={"queue": queue, "statuses": statuses, "logger": logger},
        ).start()
    queue.join()

    logger.info("ImageReplications Complete")
