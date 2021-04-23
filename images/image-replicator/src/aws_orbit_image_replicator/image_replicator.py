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


def replicate(
    config: Dict[str, Any],
    lock: synchronize.Lock,
    replications_queue: Queue,  # type: ignore
    replication_statuses: Dict[str, str],
    replicator_id: int,
) -> int:
    logger.info("Started Replicator Id: %s", replicator_id)
    replication_task: Optional[Dict[str, str]] = None

    while True:
        try:
            load_config(config["in_cluster_deployment"])

            queue_size = replications_queue.qsize()
            logger.info(f"Queue Size: {queue_size}")

            replication_task = cast(Dict[str, str], replications_queue.get(block=True, timeout=None))
            src, dest = replication_task["src"], replication_task["dest"]

            with lock:
                logger.info("Got Replication Task: %s -> %s", src, replication_task["dest"])

                status = replication_statuses[dest]
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
                    replication_statuses[dest] = f"Replicating:{attempt}"

            result = _replicate_image(config, src, dest)

            with lock:
                if result == "SUCCEEDED":
                    logger.info("Replication Complete: %s -> %s", src, dest)
                    replication_statuses[dest] = "Complete"
                else:
                    logger.error(
                        "Image Replication Attempt %s Failed: %s -> %s",
                        attempt,
                        src,
                        dest,
                    )
                    replication_statuses[dest] = f"Failed:{attempt}"

        except Exception as e:
            with lock:
                status = replication_statuses[dest]
                attempt = int(status.split(":")[1])
                logger.error(
                    "Image Replication Attempt %s Failed: %s -> %s",
                    attempt,
                    src,
                    dest,
                )
                logger.exception(e)
                replication_statuses[dest] = f"Failed:{attempt}"
        finally:
            replication_task = None
            time.sleep(5)
