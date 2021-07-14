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
import time
from multiprocessing import Queue, synchronize
from queue import Empty

from typing import Any, Dict, Optional, cast

import boto3
import yaml
from kubernetes import dynamic
from kubernetes.dynamic import exceptions as k8s_exceptions
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dump_resource, dynamic_client, logger
from urllib3.exceptions import ReadTimeoutError


def _verbosity() -> int:
    try:
        return int(os.environ.get("ORBIT_CONTROLLER_LOG_VERBOSITY", "0"))
    except Exception:
        return 0


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
                    "/var/scripts/retrieve_docker_creds.py && echo 'Docker logins successful' || echo 'Docker logins failed'",
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
    logger.debug("BuildSpec: %s", build_spec)
    return build_spec


def _replicate_image(config: Dict[str, Any], src: str, dest: str) -> str:
    logger.info("Replicating Image: %s -> %s", src, dest)

    buildspec = yaml.safe_dump(_generate_buildspec(config["repo_host"], config["repo_prefix"], src, dest))
    logger.debug("BuildSpec:\n%s", buildspec)

    client = boto3.client("codebuild")
    build_id = client.start_build(
        projectName=config["codebuild_project"],
        sourceTypeOverride="NO_SOURCE",
        buildspecOverride=buildspec,
        timeoutInMinutesOverride=config["codebuild_timeout"],
        privilegedModeOverride=True,
        imageOverride=config["codebuild_image"]
    )["build"]["id"]

    logger.info("Started CodeBuild Id: %s", build_id)

    while True:
        build = client.batch_get_builds(ids=[build_id])["builds"][0]
        status: str = build["buildStatus"]
        phase: str = build["currentPhase"]

        logger.debug("CodeBuild Id: %s, Phase: %s,  Status: %s", build_id, phase, status)

        if status == "IN_PROGRESS":
            time.sleep(10)
            continue
        else:
            return status


def get_config(workers: Optional[int] = None) -> Dict[str, Any]:
    config = {
        "repo_host": os.environ.get("IMAGE_REPLICATIONS_REPO_HOST", ""),
        "repo_prefix": os.environ.get("IMAGE_REPLICATIONS_REPO_PREFIX", ""),
        "codebuild_project": os.environ.get("IMAGE_REPLICATIONS_CODEBUILD_PROJECT", ""),
        "codebuild_timeout": int(os.environ.get("IMAGE_REPLICATIONS_CODEBUILD_TIMEOUT", "30")),
        "codebuild_image": os.environ.get("ORBIT_CODEBUILD_IMAGE", ""),
        "replicate_external_repos": os.environ.get("IMAGE_REPLICATIONS_REPLICATE_EXTERNAL_REPOS", "False").lower()
        in ["true", "yes", "1"],
        "workers": workers if workers else int(os.environ.get("IMAGE_REPLICATIONS_WATCHER_WORKERS", "2")),
    }
    return config


def get_desired_image(config: Dict[str, Any], image: str) -> str:
    external_ecr_match = re.compile(r"^[0-9]{12}\.dkr\.ecr\..+\.amazonaws.com/")
    public_ecr_match = re.compile(r"^public.ecr.aws/.+/")

    if image.startswith(config["repo_host"]):
        return image
    elif external_ecr_match.match(image):
        if config["replicate_external_repos"]:
            return external_ecr_match.sub(
                f"{config['repo_host']}/{config['repo_prefix']}/", image.replace("@sha256", "")
            )
        else:
            return image
    elif public_ecr_match.match(image):
        return public_ecr_match.sub(f"{config['repo_host']}/{config['repo_prefix']}/", image.replace("@sha256", ""))
    else:
        return f"{config['repo_host']}/{config['repo_prefix']}/{image.replace('@sha256', '')}"


def get_replication_status(
    lock: synchronize.Lock,
    queue: Queue,  # type: ignore
    statuses: Dict[str, str],
    image: str,
    desired_image: str,
) -> str:
    with lock:
        status = statuses.get(desired_image, "Unknown")

        if status == "Unknown":
            if image_replicated(desired_image):
                logger.debug("Skipping previously completed Replication Task: %s -> %s", image, desired_image)
                status = "Complete"
                statuses[desired_image] = status
            else:
                logger.debug("Queueing Replication Task: %s -> %s", image, desired_image)
                status = "Pending:1"
                statuses[desired_image] = status
                queue.put({"src": image, "dest": desired_image})
        elif status.startswith("Failed"):
            attempt = int(status.split(":")[1])
            if attempt < 3:
                attempt = attempt + 1
                logger.debug("Queueing Failed Replication Task Attemp %s: %s -> %s", attempt, image, desired_image)
                statuses[desired_image] = f"Pending:{attempt}"
                queue.put({"src": image, "dest": desired_image})
            else:
                logger.error("Too many failed replication attempts: %s -> %s", image, desired_image)

        return status


def image_replicated(image: str) -> bool:
    try:
        repo, tag = image.split(":")
        repo = "/".join(repo.split("/")[1:])
        client = boto3.client("ecr")
        paginator = client.get_paginator("list_images")
        for page in paginator.paginate(repositoryName=repo):
            for imageId in page["imageIds"]:
                if imageId.get("imageTag", None) == tag:
                    logger.debug("ECR Repository contains Image: %s", image)
                    return True
        logger.debug("Tag %s not found in ECR Repository %s", tag, repo)
        return False
    except Exception as e:
        logger.exception(e)
        return False


def create_image_replication(
    namespace: str,
    images: Dict[str, str],
    client: dynamic.DynamicClient,
    request_logger: Optional[logging.Logger] = None,
) -> None:
    _logger = request_logger if request_logger else logger
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="ImageReplication")
    image_replication = {
        "apiVersion": f"{ORBIT_API_GROUP}/{ORBIT_API_VERSION}",
        "kind": "ImageReplication",
        "metadata": {
            "generateName": "image-replication-",
        },
        "spec": {"images": [{"destination": k, "source": v} for k, v in images.items()]},
    }
    api.create(namespace=namespace, body=image_replication)
    _logger.debug("Created image_replication: %s", dump_resource(image_replication))


def delete_image_replication(
    image_replication: Dict[str, Any],
    client: dynamic.DynamicClient,
    request_logger: Optional[logging.Logger] = None,
) -> None:
    _logger = request_logger if request_logger else logger
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="ImageReplication")
    api.delete(namespace=image_replication["metadata"]["namespace"], name=image_replication["metadata"]["name"])
    _logger.debug("Deleted image_replication: %s", dump_resource(image_replication))


def watch(
    lock: synchronize.Lock,
    queue: Queue,  # type: ignore
    state: Dict[str, Any],
    statuses: Dict[str, Any],
    config: Dict[str, str],
) -> int:
    while True:
        try:
            client = dynamic_client()
            api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="ImageReplication")

            logger.info("Monitoring ImageReplications")

            kwargs = {
                "resource_version": state.get("lastResourceVersion", 0),
            }
            for event in api.watch(**kwargs):
                if _verbosity() > 2:
                    logger.debug("event object: %s", event)
                image_replication = event["raw_object"]
                state["lastResourceVersion"] = image_replication.get("metadata", {}).get("resourceVersion", 0)
                logger.debug("watcher state: %s", state)

                if event["type"] == "ADDED":
                    for image in image_replication.get("spec", {}).get("images", []):
                        status = get_replication_status(
                            lock=lock,
                            queue=queue,
                            statuses=statuses,
                            image=image["source"],
                            desired_image=image["destination"],
                        )
                        logger.info("Replication Status: %s %s", image, status)
                    delete_image_replication(image_replication=image_replication, client=client)
                else:
                    logger.debug(
                        "Skipping ImageReplication event for processing type: %s image_replication: %s",
                        event["type"],
                        dump_resource(image_replication),
                    )
        except ReadTimeoutError:
            logger.warning(
                "There was a timeout error accessing the Kubernetes API. Retrying request.",
                exc_info=True,
            )
            time.sleep(1)
        except k8s_exceptions.ApiException as ae:
            if ae.reason.startswith("Expired: too old resource version"):
                logger.warning(ae.reason)
                state["lastResourceVersion"] = 0
            else:
                logger.exception("Unknown ApiException in ImageReplicationWatcher. Failing")
                raise
        except Exception:
            logger.exception("Unknown error in ImageReplicationWatcher. Failing")
            raise
        else:
            logger.warning(
                "Watch died gracefully, starting back up with last_resource_version: %s",
                state["lastResourceVersion"],
            )


def process_image_replications(
    lock: synchronize.Lock,
    queue: Queue,  # type: ignore
    state: Dict[str, Any],
    statuses: Dict[str, Any],
    config: Dict[str, str],
    replicator_id: int,
    timeout: Optional[int] = None
) -> int:
    logger.info("Started ImageReplication Processor Id: %s", replicator_id)
    replication_task: Optional[Dict[str, str]] = None

    while True:
        try:
            queue_size = queue.qsize()
            logger.info(f"Queue Size: {queue_size}")

            replication_task = cast(Dict[str, str], queue.get(block=True, timeout=timeout))
            src, dest = replication_task["src"], replication_task["dest"]

            with lock:
                logger.info("Got Replication Task: %s -> %s", src, replication_task["dest"])

                status = statuses[dest]
                if status == "Complete":
                    logger.info("Skipping Completed Task: %s -> %s", src, dest)
                    continue
                elif status.startswith("Failed"):
                    logger.info("Skipping Failed Task: %s -> %s", src, dest)
                    continue
                elif status.startswith("Replicating"):
                    logger.info("Skipping Replicating Task: %s -> %s", src, dest)
                    continue
                else:
                    attempt = int(status.split(":")[1])
                    statuses[dest] = f"Replicating:{attempt}"

            result = _replicate_image(config, src, dest)

            with lock:
                if result == "SUCCEEDED":
                    logger.info("Replication Complete: %s -> %s", src, dest)
                    statuses[dest] = "Complete"
                else:
                    logger.error(
                        "Image Replication Attempt %s Failed: %s -> %s",
                        attempt,
                        src,
                        dest,
                    )
                    statuses[dest] = f"Failed:{attempt}"
                    queue.put(replication_task)
        except Empty as e:
            logger.debug("Queue Empty, processing Complete")
            return
        except Exception as e:
            with lock:
                status = statuses[dest]
                attempt = int(status.split(":")[1])
                logger.error(
                    "Image Replication Attempt %s Failed: %s -> %s",
                    attempt,
                    src,
                    dest,
                )
                logger.exception(e)
                statuses[dest] = f"Failed:{attempt}"
        finally:
            replication_task = None
            time.sleep(3)
