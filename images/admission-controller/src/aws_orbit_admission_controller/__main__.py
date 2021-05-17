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
from aws_orbit_admission_controller import get_module_state, load_config, logger, maintain_module_state, namespace


@click.group()
def cli() -> None:
    pass


@click.group(name="watch")
def watch() -> None:
    pass


@watch.command(name="namespaces")
@click.option("--workers", type=int, required=False, default=None, show_default=True)
def watch_namespaces(workers: Optional[int] = None) -> None:
    workers = workers if workers else int(os.environ.get("ADMISSION_CONTROLLER_WORKERS", "2"))

    logger.info("workers: %s", workers)

    load_config()
    last_state = get_module_state(module="namespaceWatcher")

    with Manager() as manager:
        sync_manager = cast(SyncManager, manager)
        work_queue = sync_manager.Queue()
        module_state = sync_manager.dict(**last_state)

        logger.info("Starting Namespace Monitoring Process")
        monitor = Process(target=namespace.watch, kwargs={"queue": work_queue, "state": module_state})
        monitor.start()

        logger.info("Starting Namespace State Updater Processs")
        state_updater = Process(target=maintain_module_state, kwargs={"module": "namespaceWatcher", "state": module_state})
        state_updater.start()

        namespace_processors = []
        for i in range(workers):
            logger.info("Starting Namespace Worker Process")
            namespace_processor = Process(
                target=namespace.process_namespaces, kwargs={"queue": work_queue, "state": module_state, "replicator_id": i}
            )
            namespace_processors.append(namespace_processor)
            namespace_processor.start()

        monitor.join()
        for namespace_processor in namespace_processors:
            namespace_processor.terminate()
        state_updater.terminate()


def main() -> int:
    logging.getLogger("click").setLevel(logging.INFO)

    cli.add_command(watch)
    cli()
    return 0
