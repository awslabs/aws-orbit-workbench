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

import time
from multiprocessing import Queue, synchronize
from typing import Any, Dict, Optional, cast

import boto3
import yaml
from aws_orbit_image_replicator import load_config, logger


def _generate_build_spec(repo_host: str, repo_prefix: str, src: str, dest: str) -> Dict[str, Any]:
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
                    f"aws ecr get-login-password | docker login --username AWS --password-stdin {repo_host}",
                    (
                        f"aws ecr create-repository --repository-name {repo} "
                        f"--tags Key=Env,Value={repo_prefix} || echo 'Already exists'",
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

    client = boto3.client("codebuild")
    build_id = client.start_build(
        projectName=config["codebuild_project"],
        sourceTypeOverride="NO_SOURCE",
        buildspecOverride=yaml.safe_dump(_generate_build_spec(config["repo_host"], config["repo_host"], src, dest)),
        timeoutInMinutesOverride=config["codebuild_timeout"],
        privilegedModeOverride=True,
    )["build"]["id"]

    logger.info("Started CodeBuild Id: %s", build_id)

    while True:
        build = client.batch_get_builds(ids=[build_id])["builds"][0]
        status: str = build["buildStatus"]

        logger.debug("CodeBuild Id: %s Status: %s", build_id, status)

        if status == "IN_PROGRESS":
            time.sleep(10)
            continue
        else:
            return status


def replicate(
    config: Dict[str, Any],
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
    replicator_id: int,
) -> int:
    logger.info("Started Replicator Id: %s", replicator_id)

    while True:
        try:
            load_config(config["in_cluster_deployment"])
            replication_task: Optional[Dict[str, str]] = None

            replication_task = cast(Dict[str, str], replications_queue.get(block=True, timeout=None))
            logger.info("Got Replication Task: %s -> %s", replication_task["src"], replication_task["dest"])

            result = _replicate_image(config, replication_task["src"], replication_task["dest"])

            with lock:
                if result == "SUCCEEDED":
                    logger.info("Replication Succeeded: %s -> %s", replication_task["src"], replication_task["dest"])
                    replication_statuses[replication_task["dest"]] = "Complete"
                else:
                    status = replication_statuses.get(replication_task["dest"], "Pending:1")
                    attempt = int(status.split(":")[1])
                    logger.error(
                        "Image Replication Attempt %s Failed: %s -> %s",
                        attempt,
                        replication_task["src"],
                        replication_task["dest"],
                    )
                    replication_statuses[replication_task["dest"]] = f"Failed:{attempt}"

        except Exception as e:
            with lock:
                replication_task = cast(Dict[str, str], replication_task)
                status = replication_statuses.get(replication_task["dest"], "Pending:1")
                attempt = int(status.split(":")[1])
                logger.error(
                    "Image Replication Attempt %s Failed: %s -> %s",
                    attempt,
                    replication_task["src"],
                    replication_task["dest"],
                )
                logger.exception(e)
                replication_statuses[replication_task["dest"]] = f"Failed:{attempt}"
