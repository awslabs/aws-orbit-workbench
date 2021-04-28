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

import re
import time
from multiprocessing import Queue, synchronize
from typing import Any, Dict, List, Tuple

import boto3
from aws_orbit_image_replicator import load_config, logger
from kubernetes.client import AppsV1Api, BatchV1Api, CoreV1Api


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


def _get_desired_image(config: Dict[str, Any], image: str) -> str:
    external_ecr_match = re.compile(r"^[0-9]{12}\.dkr\.ecr\..+\.amazonaws.com/")
    public_ecr_match = re.compile(r"^public.ecr.aws/.+/")

    if image.startswith(config["repo_host"]):
        return image
    elif external_ecr_match.match(image):
        if config["replicate_external_repos"]:
            return external_ecr_match.sub(f"{config['repo_host']}/{config['repo_prefix']}/", image)
        else:
            return image
    elif public_ecr_match.match(image):
        return public_ecr_match.sub(f"{config['repo_host']}/{config['repo_prefix']}/", image)
    else:
        return f"{config['repo_host']}/{config['repo_prefix']}/{image}"


def _get_replication_status(
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
    image: str,
    desired_image: str,
) -> str:
    with lock:
        status = replication_statuses.get(desired_image, "Unknown")

        if status == "Unknown":
            if image_replicated(desired_image):
                logger.info("Skipping previously completed Replication Task: %s -> %s", image, desired_image)
                status = "Complete"
                replication_statuses[desired_image] = status
            else:
                logger.info("Queueing Replication Task: %s -> %s", image, desired_image)
                status = "Pending:1"
                replication_statuses[desired_image] = status
                replications_queue.put({"src": image, "dest": desired_image})
        elif status.startswith("Failed"):
            attempt = int(status.split(":")[1])
            if attempt < 3:
                attempt = attempt + 1
                logger.info("Queueing Failed Replication Task Attemp %s: %s -> %s", attempt, image, desired_image)
                replication_statuses[desired_image] = f"Pending:{attempt}"
                replications_queue.put({"src": image, "dest": desired_image})
            else:
                logger.error("Too many failed replication attempts: %s -> %s", image, desired_image)

        return status


def _inspect_containers(
    config: Dict[str, Any],
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
    containers: List[Any],
) -> Tuple[List[Dict[str, str]], List[str]]:
    statuses: List[str] = []
    desired_containers: List[Dict[str, str]] = []

    for container in containers:
        name, image = (
            (container["name"], container["image"])
            if isinstance(container, dict)
            else (container.name, container.image)
        )
        desired_image = _get_desired_image(config, image)
        logger.debug("Container Image: %s -> %s", image, desired_image)
        desired_containers.append({"name": name, "image": desired_image})

        if image != desired_image:
            status = _get_replication_status(lock, replications_queue, replication_statuses, image, desired_image)
            logger.info("Image: %s -> %s, Replication Status: %s", image, desired_image, status)
            statuses.append(status)

    return desired_containers, statuses


def _inspect_deployments(
    config: Dict[str, Any],
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
) -> None:
    deployments = AppsV1Api().list_deployment_for_all_namespaces()
    for deployment in deployments.items:
        spec = deployment.spec.template.spec
        containers, statuses = _inspect_containers(
            config, lock, replications_queue, replication_statuses, spec.containers
        )
        init_containers, init_statuses = (
            _inspect_containers(config, lock, replications_queue, replication_statuses, spec.init_containers)
            if spec.init_containers
            else ([], [])
        )

        all_statuses = statuses + init_statuses
        all_containers = containers + init_containers
        if len(all_statuses) > 0 and all([status == "Complete" for status in all_statuses]):
            with lock:
                for container in all_containers:
                    del replication_statuses[container["image"]]

            body = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": containers,
                            "initContainers": init_containers,
                        }
                    }
                }
            }

            AppsV1Api().patch_namespaced_deployment(
                name=deployment.metadata.name,
                namespace=deployment.metadata.namespace,
                body=body,
            )
            logger.info(
                "Patched Deployment: %s, Namespace: %s", deployment.metadata.name, deployment.metadata.namespace
            )


def _inspect_daemon_sets(
    config: Dict[str, Any],
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
) -> None:
    daemon_sets = AppsV1Api().list_daemon_set_for_all_namespaces()
    for daemon_set in daemon_sets.items:
        spec = daemon_set.spec.template.spec
        containers, statuses = _inspect_containers(
            config, lock, replications_queue, replication_statuses, spec.containers
        )
        init_containers, init_statuses = (
            _inspect_containers(config, lock, replications_queue, replication_statuses, spec.init_containers)
            if spec.init_containers
            else ([], [])
        )

        all_statuses = statuses + init_statuses
        all_containers = containers + init_containers
        if len(all_statuses) > 0 and all([status == "Complete" for status in all_statuses]):
            with lock:
                for container in all_containers:
                    del replication_statuses[container["image"]]

            body = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": containers,
                            "initContainers": init_containers,
                        }
                    }
                }
            }

            AppsV1Api().patch_namespaced_daemon_set(
                name=daemon_set.metadata.name,
                namespace=daemon_set.metadata.namespace,
                body=body,
            )
            logger.info(
                "Patched Daemon Set: %s, Namespace: %s", daemon_set.metadata.name, daemon_set.metadata.namespace
            )


def _inspect_jobs(
    config: Dict[str, Any],
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
) -> None:
    jobs = BatchV1Api().list_job_for_all_namespaces()
    for job in jobs.items:
        spec = job.spec.template.spec
        containers, statuses = _inspect_containers(
            config, lock, replications_queue, replication_statuses, spec.containers
        )
        init_containers, init_statuses = (
            _inspect_containers(config, lock, replications_queue, replication_statuses, spec.init_containers)
            if spec.init_containers
            else ([], [])
        )

        all_statuses = statuses + init_statuses
        all_containers = containers + init_containers
        if len(all_statuses) > 0 and all([status == "Complete" for status in all_statuses]):
            with lock:
                for container in all_containers:
                    del replication_statuses[container["image"]]

            body = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": containers,
                            "initContainers": init_containers,
                        }
                    }
                }
            }

            BatchV1Api().patch_namespaced_job(
                name=job.metadata.name,
                namespace=job.metadata.namespace,
                body=body,
            )
            logger.info("Patched Deployment: %s, Namespace: %s", job.metadata.name, job.metadata.namespace)


def _inspect_standalone_pods(
    config: Dict[str, Any],
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
) -> None:
    pods = CoreV1Api().list_pod_for_all_namespaces()
    for pod in pods.items:
        if pod.metadata.owner_references:
            owner_reference = pod.metadata.owner_references[0]
            if owner_reference.kind != "Job":
                logger.debug("Skipping Owned Pod: %s/%s", pod.metadata.namespace, pod.metadata.name)
                continue
            else:
                logger.info(
                    "Found Pod: %s/%s for Job: %s", pod.metadata.namespace, pod.metadata.name, owner_reference.name
                )

        spec = pod.spec
        containers, statuses = _inspect_containers(
            config, lock, replications_queue, replication_statuses, spec.containers
        )
        init_containers, init_statuses = (
            _inspect_containers(config, lock, replications_queue, replication_statuses, spec.init_containers)
            if spec.init_containers
            else ([], [])
        )

        all_statuses = statuses + init_statuses
        all_containers = containers + init_containers
        if len(all_statuses) > 0 and all([status == "Complete" for status in all_statuses]):
            with lock:
                for container in all_containers:
                    del replication_statuses[container["image"]]

            body = {
                "spec": {
                    "containers": containers,
                    "initContainers": init_containers,
                }
            }

            CoreV1Api().patch_namespaced_pod(
                name=pod.metadata.name,
                namespace=pod.metadata.namespace,
                body=body,
            )
            logger.info("Patched Pod: %s, Namespace: %s", pod.metadata.name, pod.metadata.namespace)


def monitor(
    config: Dict[str, Any],
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
) -> int:
    try:
        while True:
            load_config(config["in_cluster_deployment"])

            logger.debug("Monitoring Deployments")
            _inspect_deployments(config, lock, replications_queue, replication_statuses)

            logger.debug("Monitoring Daemon Sets")
            _inspect_daemon_sets(config, lock, replications_queue, replication_statuses)

            # logger.debug("Monitoring Jobs")
            # _inspect_jobs(config, lock, replications_queue, replication_statuses)

            logger.debug("Monitoring Standalone Pods")
            _inspect_standalone_pods(config, lock, replications_queue, replication_statuses)

            time.sleep(20)
    except Exception as e:
        logger.exception(e)
        return -1
