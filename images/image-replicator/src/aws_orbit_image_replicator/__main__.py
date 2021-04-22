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
from multiprocessing import Manager, Process
from multiprocessing.managers import SyncManager
from typing import Dict, Optional, cast

import click
from aws_orbit_image_replicator import image_monitor, image_replicator, logger


@click.command()
@click.option("--repo-host", type=str, required=False, default=None, show_default=True)
@click.option("--repo-prefix", type=str, required=False, default=None, show_default=True)
@click.option("--codebuild-project", type=str, required=False, default=None, show_default=True)
@click.option("--codebuild-timeout", type=int, required=False, default=None, show_default=True)
@click.option(
    "--replicate-internal-repos/--skip-internal-repos",
    type=bool,
    required=False,
    default=None,
    show_default=True,
)
@click.option(
    "--in-cluster-deployment/--external-deployment",
    type=bool,
    required=False,
    default=None,
    show_default=True,
)
@click.option("--replicator-processes", type=int, required=False, default=None, show_default=True)
@click.option("--debug/--no-debug", type=bool, required=False, default=False, show_default=True)
def main(
    repo_host: Optional[str],
    repo_prefix: Optional[str],
    codebuild_project: Optional[str],
    codebuild_timeout: Optional[int],
    replicate_internal_repos: Optional[bool],
    in_cluster_deployment: Optional[bool],
    replicator_processes: Optional[int],
    debug: bool,
) -> int:
    if debug:
        logger.setLevel(logging.DEBUG)

    repo_host = repo_host if repo_host else os.environ.get("IMAGE_REPLICATOR_REPO_HOST", None)
    repo_prefix = repo_prefix if repo_prefix else os.environ.get("IMAGE_REPLICATOR_REPO_PREFIX", None)
    codebuild_project = codebuild_project if codebuild_project else os.environ.get("IMAGE_REPLICATOR_CODEBUILD_PROJECT", None)
    codebuild_timeout = codebuild_timeout if codebuild_timeout else int(os.environ.get("IMAGE_REPLICATOR_CODEBUILD_TIMEOUT", "30"))
    replicate_internal_repos = (
        replicate_internal_repos
        if replicate_internal_repos is not None
        else os.environ.get("IMAGE_REPLICATOR_REPLICATE_INTERNAL_REPOS", False)
    )
    in_cluster_deployment = (
        in_cluster_deployment
        if in_cluster_deployment is not None
        else os.environ.get("IMAGE_REPLICATOR_IN_CLUSTER_DEPLOYMENT", True)
    )
    replicator_processes = (
        replicator_processes if replicator_processes else int(os.environ.get("IMAGE_REPLICATOR_REPLICATOR_PROCESSES", "3"))
    )

    logger.info("repo_host: %s", repo_host)
    logger.info("repo_prefix: %s", repo_prefix)
    logger.info("codebuild_project: %s", codebuild_project)
    logger.info("codebuild_timeout: %s", codebuild_timeout)
    logger.info("replicate_internal_repos: %s", replicate_internal_repos)
    logger.info("in_cluster_deployment: %s", in_cluster_deployment)
    logger.info("replicator_processes: %s", replicator_processes)

    if not repo_host or not repo_prefix or not codebuild_project or not codebuild_timeout or not replicator_processes:
        exception = click.ClickException("All of repo_host, repo_prefix, codebuild_project, codebuild_timeout, and replicator_processes are required.")
        logger.error(exception)
        raise exception

    with Manager() as manager:
        sync_manager = cast(SyncManager, manager)
        lock = sync_manager.Lock()
        replications_queue = sync_manager.Queue()
        replication_statuses: Dict[str, str] = sync_manager.dict()
        config = {
            "repo_host": repo_host,
            "repo_prefix": repo_prefix,
            "codebuild_project": codebuild_project,
            "codebuild_timeout": codebuild_timeout,
            "replicate_internal_repos": replicate_internal_repos,
            "in_cluster_deployment": in_cluster_deployment,
            "replicator_processes": replicator_processes,
        }

        logger.info("Starting Monitoring Process")
        monitor = Process(
            target=image_monitor.monitor,
            kwargs={
                "config": config,
                "lock": lock,
                "replications_queue": replications_queue,
                "replication_statuses": replication_statuses,
            },
        )
        monitor.start()

        replicators = []
        for i in range(replicator_processes):
            logger.info("Starting Replication Process: %s", i)
            replicator = Process(
                target=image_replicator.replicate,
                kwargs={
                    "config": config,
                    "lock": lock,
                    "replications_queue": replications_queue,
                    "replication_statuses": replication_statuses,
                    "replicator_id": i,
                },
            )
            replicators.append(replicator)
            replicator.start()

        result = monitor.join()
        for replicator in replicators:
            replicator.terminate()

    if result == 0:
        return result
    else:
        raise click.ClickException("Processing Error")


if __name__ == "__main__":
    logging.getLogger("click").setLevel(logging.INFO)
    main()
