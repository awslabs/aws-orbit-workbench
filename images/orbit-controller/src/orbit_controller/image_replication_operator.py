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

import asyncio
import logging
import os
import re
import threading
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
        "repo_host": os.environ.get("IMAGE_REPLICATIONS_REPO_HOST", ""),
        "repo_prefix": os.environ.get("IMAGE_REPLICATIONS_REPO_PREFIX", ""),
        "codebuild_project": os.environ.get("IMAGE_REPLICATIONS_CODEBUILD_PROJECT", ""),
        "codebuild_timeout": int(os.environ.get("IMAGE_REPLICATIONS_CODEBUILD_TIMEOUT", "30")),
        "codebuild_image": os.environ.get("ORBIT_CODEBUILD_IMAGE", ""),
        "replicate_external_repos": os.environ.get("IMAGE_REPLICATIONS_REPLICATE_EXTERNAL_REPOS", "False").lower()
        in ["true", "yes", "1"],
        "workers": int(os.environ.get("IMAGE_REPLICATIONS_WORKERS", "2")),
        "max_replication_attempts": int(os.environ.get("IMAGE_REPLICATIONS_MAX_REPLICATION_ATTEMPTS", "3")),
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
) -> None:
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="ImageReplication")
    image_replication = {
        "apiVersion": f"{ORBIT_API_GROUP}/{ORBIT_API_VERSION}",
        "kind": "ImageReplication",
        "metadata": {
            "generateName": "image-replication-",
        },
        "spec": {"destination": destination, "source": source},
    }
    api.create(namespace=namespace, body=image_replication)
    logger.debug("Created ImageReplication source: %s destination: %s", source, destination)


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
        return False


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, logger: kopf.Logger, **_: Any) -> None:
    settings.admission.server = kopf.WebhookServer(
        cafile="/certs/ca.crt", certfile="/certs/tls.crt", pkeyfile="/certs/tls.key", port=443
    )
    settings.persistence.progress_storage = kopf.MultiProgressStorage([
        kopf.AnnotationsProgressStorage(prefix='orbit.aws'),
        kopf.StatusProgressStorage(field='status.orbit-aws'),
    ])
    settings.posting.level = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO"))

    global LOCK
    LOCK = threading.Lock()

    global CONFIG
    CONFIG = _get_config()
    logger.info("CONFIG: %s", CONFIG)

    global WORKERS_IN_PROCESS
    WORKERS_IN_PROCESS = 0


@kopf.index(ORBIT_API_GROUP, ORBIT_API_VERSION, "imagereplications")  # type: ignore
def imagereplications_idx(spec: kopf.Spec, uid: str, status: kopf.Status, **_: Any) -> Dict[str, str]:
    scheduler_status = status.get("scheduler", {}).get("replication", None)
    monitor_status = status.get("codebuild_monitor", {}).get("replication", None)
    return {spec["source"]: {"uid": uid, "destination": spec["destination"], "scheduler_status": scheduler_status, "monitor_status": monitor_status}}


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
                dest_containers.append({"name": container["name"], "image": desired_image})
                replications[image] = desired_image
                annotations[f"original-container-image~1{container['name']}"] = image

    process_containers(spec.get("initContainers", []), init_containers)
    process_containers(spec.get("containers", []), containers)

    if replications:
        client = dynamic_client()
        for source, destination in replications.items():
            if not imagereplications_idx.get(source, []):
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


@kopf.on.resume(ORBIT_API_GROUP, ORBIT_API_VERSION, "imagereplications")  # type: ignore
@kopf.on.create(ORBIT_API_GROUP, ORBIT_API_VERSION, "imagereplications", )
def replication_checker(spec: kopf.Spec, logger: kopf.Logger, **_: Any) -> str:
    if _image_replicated(image=spec["destination"], logger=logger):
        logger.info("Skipped: Image previously replicated to ECR")
        return {"replication": "Skipped", "reason": "Image previously replicated to ECR"}
    logger.info("Starting Replication")
    return {"replication": "Started"}


def _is_new_replication(status: kopf.Status, **_: Any) -> bool:
    return cast(bool, status.get("replication_checker", {}).get("replication", None) == "Started")


def _can_schedule(status: kopf.Status, **_: Any) -> bool:
    scheduler_status = status.get("scheduler", {}).get("replication", None)
    monitor_status = status.get("codebuild_monitor", {}).get("replication", None)
    return scheduler_status not in ["Scheduled", "MaxAttemptsExceeded"] and monitor_status not in [
        "SUCCEEDED",
        "IN_PROGRESS",
    ]


@kopf.timer(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "imagereplications",
    interval=3,
    when=kopf.all_([_is_new_replication, _can_schedule]),
)
def scheduler(status: kopf.Status, logger: kopf.Logger, **_: Any) -> Dict[str, Any]:
    attempt = len(status.get("codebuild_runner/status.scheduler", [])) + 1
    if attempt > CONFIG["max_replication_attempts"]:
        return {"replication": "MaxAttemptsExceeded", "attempt": attempt}

    with LOCK:
        global WORKERS_IN_PROCESS
        logger.debug("WORKERS_IN_PROCESS: %s", WORKERS_IN_PROCESS)
        if WORKERS_IN_PROCESS < CONFIG["workers"]:
            WORKERS_IN_PROCESS += 1
            logger.info("Scheduled Attempt: %s", attempt)
            return {"replication": "Scheduled", "attempt": attempt, "workers_in_process": WORKERS_IN_PROCESS}
        else:
            return {"replication": "Pending", "attempt": attempt, "workers_in_process": WORKERS_IN_PROCESS}


@kopf.on.field(ORBIT_API_GROUP, ORBIT_API_VERSION, "imagereplications", field="status.scheduler")  # type: ignore
def codebuild_runner(
    spec: kopf.Spec, new: Dict[str, Any], status: kopf.Status, logger: kopf.Logger, **_: Any
) -> List[Dict[str, Optional[str]]]:
    runners: List[Dict[str, Optional[str]]] = status.get("codebuild_runner/status.scheduler", [])
    if new.get("replication", None) == "Scheduled":
        build_id, error = _replicate_image(src=spec["source"], dest=spec["destination"])
        replication = "Replicating" if error is None else "Error"
        runners.append({"replication": replication, "codebuild_id": build_id, "error": error})
        logger.info("CodeBuildId: %s Error: %s", build_id, error)

    if error:
        with LOCK:
            global WORKERS_IN_PROCESS
            WORKERS_IN_PROCESS -= 1

    return runners


def _requires_monitoring(status: kopf.Status, **_: Any) -> bool:
    runner_status = status.get("codebuild_runner/status.scheduler", [{}])[-1].get("replication", None)
    monitor_status = status.get("codebuild_monitor", {}).get("replication", None)
    return runner_status == "Replicating" and monitor_status in ["IN_PROGRESS", None]


@kopf.on.timer(ORBIT_API_GROUP, ORBIT_API_VERSION, "imagereplications", interval=10, when=_requires_monitoring)
def codebuild_monitor(status: kopf.Status, logger: kopf.Logger, **_: Any) -> Dict[str, str]:
    build_id = status.get("codebuild_runner/status.scheduler", [{}])[-1].get("codebuild_id", None)

    client = boto3.client("codebuild")
    build = client.batch_get_builds(ids=[build_id])["builds"][0]
    build_status: str = build["buildStatus"]
    phase: str = build["currentPhase"]

    if build_status != "IN_PROGRESS":
        logger.info("CodeBuildId: %s BuildStatus: %s", build_id, build_status)
        with LOCK:
            global WORKERS_IN_PROCESS
            WORKERS_IN_PROCESS -= 1

    return {"replication": build_status, "phase": phase, "codebuild_id": build_id}
