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
import re
import threading
import time
from copy import deepcopy
from queue import Queue
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import boto3
import kopf
import yaml
from kubernetes import dynamic
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dynamic_client

LOCK: threading.Lock
CONFIG: Dict[str, Any]
WORKERS_IN_PROCESS: int = 0


def _get_config() -> Dict[str, Any]:
    config = {
        "repo_host": os.environ.get("REPO_HOST", ""),
        "repo_prefix": os.environ.get("REPO_PREFIX", ""),
        "codebuild_project": os.environ.get("CODEBUILD_PROJECT", ""),
        "codebuild_timeout": int(os.environ.get("CODEBUILD_TIMEOUT", "30")),
        "codebuild_image": os.environ.get("ORBIT_CODEBUILD_IMAGE", ""),
        "replicate_external_repos": os.environ.get("REPLICATE_EXTERNAL_REPOS", "False").lower() in ["true", "yes", "1"],
        "workers": int(os.environ.get("WORKERS", "4")),
        "max_replication_attempts": int(os.environ.get("MAX_REPLICATION_ATTEMPTS", "3")),
    }
    return config


def _generate_buildspec(repo_host: str, repo_prefix: str, src: str, dest: str) -> Dict[str, Any]:
    repo = dest.replace(f"{repo_host}/", "").split(":")[0]
    build_spec = {
        "version": 0.2,
        "phases": {
            "install": {
                "runtime-versions": {"python": 3.7, "docker": 19},
                "commands": [
                    (
                        "nohup /usr/sbin/dockerd --host=unix:///var/run/docker.sock "
                        "--host=tcp://0.0.0.0:2375 --storage-driver=overlay&"
                    ),
                    'timeout 15 sh -c "until docker info; do echo .; sleep 1; done"',
                ],
            },
            "pre_build": {
                "commands": [
                    "/var/scripts/retrieve_docker_creds.py && echo 'Docker logins successful' "
                    "|| echo 'Docker logins failed'",
                    f"aws ecr get-login-password | docker login --username AWS --password-stdin {repo_host}",
                    (
                        f"aws ecr create-repository --repository-name {repo} "
                        f"--tags Key=Env,Value={repo_prefix} || echo 'Already exists'"
                    ),
                ]
            },
            "build": {"commands": [f"docker pull {src}", f"docker tag {src} {dest}", f"docker push {dest}"]},
        },
    }
    return build_spec


def _replicate_image(src: str, dest: str) -> Tuple[Optional[str], Optional[str]]:
    buildspec = yaml.safe_dump(_generate_buildspec(CONFIG["repo_host"], CONFIG["repo_prefix"], src, dest))

    try:
        client = boto3.client("codebuild")
        build_id = client.start_build(
            projectName=CONFIG["codebuild_project"],
            sourceTypeOverride="NO_SOURCE",
            buildspecOverride=buildspec,
            timeoutInMinutesOverride=CONFIG["codebuild_timeout"],
            privilegedModeOverride=True,
            imageOverride=CONFIG["codebuild_image"],
        )["build"]["id"]
        return build_id, None
    except Exception as e:
        return None, str(e)


def _get_desired_image(image: str) -> str:
    external_ecr_match = re.compile(r"^[0-9]{12}\.dkr\.ecr\..+\.amazonaws.com/")
    public_ecr_match = re.compile(r"^public.ecr.aws/.+/")

    if image.startswith(CONFIG["repo_host"]):
        return image
    elif external_ecr_match.match(image):
        if CONFIG["replicate_external_repos"]:
            return external_ecr_match.sub(
                f"{CONFIG['repo_host']}/{CONFIG['repo_prefix']}/", image.replace("@sha256", "")
            )
        else:
            return image
    elif public_ecr_match.match(image):
        return public_ecr_match.sub(f"{CONFIG['repo_host']}/{CONFIG['repo_prefix']}/", image.replace("@sha256", ""))
    else:
        return f"{CONFIG['repo_host']}/{CONFIG['repo_prefix']}/{image.replace('@sha256', '')}"


def _create_image_replication(
    namespace: str,
    source: str,
    destination: str,
    client: dynamic.DynamicClient,
    logger: Union[kopf.Logger, logging.Logger],
) -> Tuple[str, str]:
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="ImageReplication")
    image_replication = {
        "apiVersion": f"{ORBIT_API_GROUP}/{ORBIT_API_VERSION}",
        "kind": "ImageReplication",
        "metadata": {
            "generateName": "image-replication-",
        },
        "spec": {"destination": destination, "source": source},
    }
    result = api.create(namespace=namespace, body=image_replication).to_dict()
    logger.debug("Created ImageReplication: %s", result)
    metadata = result.get("metadata", {})
    return metadata.get("namespace", None), metadata.get("name", None)


def _image_replicated(image: str, logger: Union[kopf.Logger, logging.Logger]) -> bool:
    try:
        repo, tag = image.split(":")
        repo = "/".join(repo.split("/")[1:])
        client = boto3.client("ecr")
        paginator = client.get_paginator("list_images")
        for page in paginator.paginate(repositoryName=repo):
            for imageId in page["imageIds"]:
                if imageId.get("imageTag", None) == tag:
                    logger.info("ECR Repository contains Image: %s", image)
                    return True
        logger.debug("Tag %s not found in ECR Repository %s", tag, repo)
        return False
    except Exception as e:
        logger.warn(str(e))
        return False


def _patch_imagereplication(
    namespace: str,
    name: str,
    patch: Dict[str, Any],
    client: dynamic.DynamicClient,
    logger: Union[kopf.Logger, logging.Logger],
) -> None:
    api = client.resources.get(group=ORBIT_API_GROUP, api_version=ORBIT_API_VERSION, kind="ImageReplication")
    logger.debug("Patching %s/%s with %s", namespace, name, patch)
    api.patch(namespace=namespace, name=name, body=patch, content_type="application/merge-patch+json")


def _update_imagereplication_status(
    namespace: str,
    name: str,
    status: Dict[str, str],
    client: dynamic.DynamicClient,
    logger: Union[kopf.Logger, logging.Logger],
) -> None:
    _patch_imagereplication(
        namespace=namespace,
        name=name,
        client=client,
        logger=logger,
        patch={"status": status},
    )


def _set_globals(logger: Union[kopf.Logger, logging.Logger]) -> None:
    global LOCK
    LOCK = threading.Lock()

    global CONFIG
    CONFIG = _get_config()
    logger.info("CONFIG: %s", CONFIG)

    global WORKERS_IN_PROCESS
    WORKERS_IN_PROCESS = 0


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
    _set_globals(logger=logger)


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
    imagereplications_idx: kopf.Index[str, List[str]],
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
            desired_image = _get_desired_image(image=image)
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
                _create_image_replication(
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


@kopf.on.resume(ORBIT_API_GROUP, ORBIT_API_VERSION, "imagereplications", field="status.replication", value=kopf.ABSENT)
@kopf.on.create(ORBIT_API_GROUP, ORBIT_API_VERSION, "imagereplications", field="status.replication", value=kopf.ABSENT)
def replication_checker(spec: kopf.Spec, status: kopf.Status, patch: kopf.Patch, logger: kopf.Logger, **_: Any) -> str:
    if status.get("replication", None) is not None:
        return cast(str, status["replication"].get("replicationStatus", "Unknown"))

    replication = {}
    if _image_replicated(image=spec["destination"], logger=logger):
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
        return cast(bool, replication_status == "Failed" and attempt <= CONFIG["max_replication_attempts"])
    else:
        return False


@kopf.timer(ORBIT_API_GROUP, ORBIT_API_VERSION, "imagereplications", interval=5, when=_needs_rescheduling)
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
def codebuild_runner(spec: kopf.Spec, patch: kopf.Patch, status: kopf.Status, logger: kopf.Logger, **_: Any) -> str:
    replication = status.get("replication", {})

    build_id, error = _replicate_image(src=spec["source"], dest=spec["destination"])

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
            {"codeBuildId": build_id, "codeBuildStatus": build["buildStatus"], "codeBuildPhase": build["currentPhase"]}
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
            namespace, name = _create_image_replication(
                namespace="orbit-system", source=source, destination=destination, client=client, logger=logger
            )
            statuses[destination]["namespace"] = namespace
            statuses[destination]["name"] = name
            logger.debug("New Status: %s", status)
        else:
            replication_status = status.get("status", {}).get("replication", {}).get("replicationStatus", None)

        status = {**status, **patch}
        _update_imagereplication_status(
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
        _update_imagereplication_status(
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
            spec=cast(kopf.Spec, spec), status=status["status"], patch=cast(kopf.Patch, patch), logger=logger
        )
        status = {**status, **patch}
        _update_imagereplication_status(
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
        _update_imagereplication_status(
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
        _update_imagereplication_status(
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
            desired_image = _get_desired_image(image=source_image)
            if source_image != desired_image:
                logger.debug("Queueing: %s", desired_image)
                statuses[desired_image] = {"source": source_image, "destination": desired_image, "status": None}
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
