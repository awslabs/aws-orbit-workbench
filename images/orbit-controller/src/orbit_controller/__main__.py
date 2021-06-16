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
from typing import Any, Dict, Optional, cast

import click
from orbit_controller import (
    get_module_state,
    image_replication,
    load_config,
    logger,
    maintain_module_state,
    namespace,
    pod_default,
    pod_setting,
)


@click.group()
def cli() -> None:
    pass


@click.group(name="watch")
def watch() -> None:
    pass


@watch.command(name="namespaces")
@click.option("--workers", type=int, required=False, default=None, show_default=True)
def watch_namespaces(workers: Optional[int] = None) -> None:
    workers = workers if workers else int(os.environ.get("USERSPACE_CHART_MANAGER_WORKERS", "2"))

    logger.info("workers: %s", workers)

    load_config()
    last_state = get_module_state(module="userspaceChartManager")

    with Manager() as manager:
        sync_manager = cast(SyncManager, manager)
        work_queue = sync_manager.Queue()
        module_state = sync_manager.dict(**last_state)

        logger.info("Starting Namespace Monitoring Process")
        monitor = Process(target=namespace.watch, kwargs={"queue": work_queue, "state": module_state})
        monitor.start()

        logger.info("Starting Namespace State Updater Process")
        state_updater = Process(
            target=maintain_module_state,
            kwargs={"module": "userspaceChartManager", "state": module_state},
        )
        state_updater.start()

        namespace_processors = []
        for i in range(workers):
            logger.info("Starting Namespace Worker Process")
            namespace_processor = Process(
                target=namespace.process_namespaces,
                kwargs={"queue": work_queue, "state": module_state, "replicator_id": i},
            )
            namespace_processors.append(namespace_processor)
            namespace_processor.start()

        monitor.join()
        for namespace_processor in namespace_processors:
            namespace_processor.terminate()
        state_updater.terminate()


@watch.command(name="podsettings")
@click.option("--workers", type=int, required=False, default=None, show_default=True)
def watch_pod_settings(workers: Optional[int] = None) -> None:
    workers = workers if workers else int(os.environ.get("POD_SETTINGS_WATCHER_WORKERS", "2"))

    logger.info("workers: %s", workers)

    load_config()
    last_state = get_module_state(module="podsettingsWatcher")

    with Manager() as manager:
        sync_manager = cast(SyncManager, manager)
        work_queue = sync_manager.Queue()
        module_state = sync_manager.dict(**last_state)

        logger.info("Starting PodSettings Monitoring Process")
        monitor = Process(target=pod_setting.watch, kwargs={"queue": work_queue, "state": module_state})
        monitor.start()

        logger.info("Starting PodSettings State Updater Process")
        state_updater = Process(
            target=maintain_module_state,
            kwargs={"module": "podsettingsWatcher", "state": module_state},
        )
        state_updater.start()

        pod_settings_processors = []
        for i in range(workers):
            logger.info("Starting PodSettings Worker Process")
            pod_settings_processor = Process(
                target=pod_setting.process_pod_settings,
                kwargs={"queue": work_queue, "state": module_state, "replicator_id": i},
            )
            pod_settings_processors.append(pod_settings_processor)
            pod_settings_processor.start()

        monitor.join()
        for pod_settings_processor in pod_settings_processors:
            pod_settings_processor.terminate()
        state_updater.terminate()


@watch.command(name="poddefaults")
@click.option("--workers", type=int, required=False, default=None, show_default=True)
def watch_pod_defaults(workers: Optional[int] = None) -> None:
    workers = workers if workers else int(os.environ.get("POD_DEFAULTS_WATCHER_WORKERS", "2"))

    logger.info("workers: %s", workers)

    load_config()
    last_state = get_module_state(module="poddefaultsWatcher")

    with Manager() as manager:
        sync_manager = cast(SyncManager, manager)
        work_queue = sync_manager.Queue()
        module_state = sync_manager.dict(**last_state)

        logger.info("Starting PodDefaults Monitoring Process")
        monitor = Process(target=pod_default.watch, kwargs={"queue": work_queue, "state": module_state})
        monitor.start()

        logger.info("Starting PodDefaults State Updater Process")
        state_updater = Process(
            target=maintain_module_state,
            kwargs={"module": "poddefaultsWatcher", "state": module_state},
        )
        state_updater.start()

        pod_defaults_processors = []
        for i in range(workers):
            logger.info("Starting PodDefaults Worker Process")
            pod_defaults_processor = Process(
                target=pod_default.process_pod_defaults,
                kwargs={"queue": work_queue, "state": module_state, "replicator_id": i},
            )
            pod_defaults_processors.append(pod_defaults_processor)
            pod_defaults_processor.start()

        monitor.join()
        for pod_defaults_processor in pod_defaults_processors:
            pod_defaults_processor.terminate()
        state_updater.terminate()


@watch.command(name="imagereplications")
@click.option("--workers", type=int, required=False, default=None, show_default=True)
def watch_image_replications(workers: Optional[int] = None) -> None:
    load_config()
    last_state = get_module_state(module="imagereplicationsWatcher")

    config = image_replication.get_config(workers)
    logger.info("config: %s", config)

    if any([v is None for v in config.values()]):
        exception = click.ClickException(
            "All of repo_host, repo_prefix, codebuild_project, codebuild_timeout, " "and workers are required."
        )
        logger.error(exception)
        raise exception

    with Manager() as manager:
        sync_manager = cast(SyncManager, manager)
        lock = sync_manager.Lock()
        work_queue = sync_manager.Queue()
        module_state = sync_manager.dict(**last_state)
        replication_statuses: Dict[str, Any] = sync_manager.dict()

        logger.info("Starting ImageReplications Monitoring Process")
        monitor = Process(
            target=image_replication.watch,
            kwargs={
                "lock": lock,
                "queue": work_queue,
                "state": module_state,
                "statuses": replication_statuses,
                "config": config,
            },
        )
        monitor.start()

        logger.info("Starting ImageReplications State Updater Process")
        state_updater = Process(
            target=maintain_module_state,
            kwargs={"module": "imagereplicationsWatcher", "state": module_state},
        )
        state_updater.start()

        image_replications_processors = []
        for i in range(config["workers="]):
            logger.info("Starting ImageReplications Worker Process")
            image_replications_processor = Process(
                target=image_replication.process_image_replications,
                kwargs={
                    "lock": lock,
                    "queue": work_queue,
                    "state": module_state,
                    "statuses": replication_statuses,
                    "config": config,
                    "replicator_id": i,
                },
            )
            image_replications_processors.append(image_replications_processor)
            image_replications_processor.start()

        monitor.join()
        for image_replications_processor in image_replications_processors:
            image_replications_processor.terminate()
        state_updater.terminate()


def main() -> int:
    logging.getLogger("click").setLevel(logging.INFO)

    cli.add_command(watch)
    cli()
    return 0
