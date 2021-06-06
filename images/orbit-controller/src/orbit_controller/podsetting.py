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

import os
import time
from multiprocessing import Queue
from typing import Any, Dict, Optional, cast

from kubernetes.dynamic import exceptions as k8s_exceptions
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dump_resource, dynamic_client, logger, poddefault
from urllib3.exceptions import ReadTimeoutError


def _verbosity() -> int:
    try:
        return int(os.environ.get("ORBIT_CONTROLLER_LOG_VERBOSITY", "0"))
    except Exception:
        return 0


def process_added_event(podsetting: Dict[str, Any]) -> None:
    name = podsetting["metadata"]["name"]
    namespace = podsetting["metadata"]["namespace"]
    desc = podsetting["spec"].get("desc", "")
    client = dynamic_client()

    try:
        poddefault.create_poddefault(
            namespace=namespace,
            poddefault=poddefault.construct(name=name, desc=desc, labels={"orbit/space": "team"}),
            client=client,
        )
        logger.debug("ADDED poddefault for podsetting: %s", dump_resource(podsetting))
    except Exception:
        if _verbosity() > 0:
            logger.exception(
                "IGNORING ERROR ADDING poddefault for podsetting: %s",
                dump_resource(podsetting),
            )
        else:
            logger.error(
                "IGNORING ERROR ADDING poddefault for podsetting: %s",
                dump_resource(podsetting),
            )


def process_modified_event(podsetting: Dict[str, Any]) -> None:
    name = podsetting["metadata"]["name"]
    namespace = podsetting["metadata"]["namespace"]
    desc = podsetting["spec"].get("desc", "")
    client = dynamic_client()

    try:
        poddefault.modify_poddefault(namespace=namespace, name=name, desc=desc, client=client)
        logger.debug("MODIFIED poddefault for podsetting: %s", dump_resource(podsetting))
    except Exception:
        if _verbosity() > 0:
            logger.exception(
                "IGNORING ERROR MODIFIYING poddefault for podsetting: %s",
                dump_resource(podsetting),
            )
        else:
            logger.error(
                "IGNORING ERROR MODIFIYING poddefault for podsetting: %s",
                dump_resource(podsetting),
            )


def process_deleted_event(podsetting: Dict[str, Any]) -> None:
    name = podsetting["metadata"]["name"]
    namespace = podsetting["metadata"]["namespace"]
    client = dynamic_client()

    try:
        poddefault.delete_poddefault(namespace=namespace, name=name, client=client)
        logger.debug("DELETED poddefault for podsetting: %s", dump_resource(podsetting))
    except Exception:
        if _verbosity() > 0:
            logger.exception(
                "IGNORING ERROR DELETING poddefault for podsetting: %s",
                dump_resource(podsetting),
            )
        else:
            logger.error(
                "IGNORING ERROR DELETING poddefault for podsetting: %s",
                dump_resource(podsetting),
            )


def watch(queue: Queue, state: Dict[str, Any]) -> int:  # type: ignore
    while True:
        try:
            client = dynamic_client()
            api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="PodSetting")

            logger.info("Monitoring PodSettings")

            kwargs = {
                "resource_version": state.get("lastResourceVersion", 0),
            }
            for event in api.watch(**kwargs):
                if _verbosity() > 2:
                    logger.debug("event object: %s", event)
                podsetting = event["raw_object"]
                state["lastResourceVersion"] = podsetting.get("metadata", {}).get("resourceVersion", 0)
                logger.debug("watcher state: %s", state)
                queue_event = {"type": event["type"], "raw_object": event["raw_object"]}

                labels = event["raw_object"].get("metadata", {}).get("labels", {})
                if labels.get("orbit/space") == "team" and "orbit/disable-watcher" not in labels:
                    logger.debug(
                        "Queueing PodSetting event for processing type: %s podsetting: %s",
                        event["type"],
                        dump_resource(event["raw_object"]),
                    )
                    queue.put(queue_event)
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
                logger.exception("Unknown ApiException in PodSettingWatcher. Failing")
                raise
        except Exception:
            logger.exception("Unknown error in PodSettingWatcher. Failing")
            raise
        else:
            logger.warning(
                "Watch died gracefully, starting back up with last_resource_version: %s",
                state["lastResourceVersion"],
            )


def process_podsettings(queue: Queue, state: Dict[str, Any], replicator_id: int) -> int:  # type: ignore
    logger.info("Started PodSetting Processor Id: %s", replicator_id)
    podsetting_event: Optional[Dict[str, Any]] = None

    while True:
        try:
            podsetting_event = cast(Dict[str, Any], queue.get(block=True, timeout=None))

            if podsetting_event["type"] == "ADDED":
                process_added_event(podsetting=podsetting_event["raw_object"])
            elif podsetting_event["type"] == "MODIFIED":
                process_modified_event(podsetting=podsetting_event["raw_object"])
            elif podsetting_event["type"] == "DELETED":
                process_deleted_event(podsetting=podsetting_event["raw_object"])
            else:
                logger.debug("Skipping PodSetting event: %s", dump_resource(podsetting_event))
        except Exception:
            logger.exception(
                "Failed to process PodSetting event: %s",
                dump_resource(podsetting_event),
            )
        finally:
            podsetting_event = None
            time.sleep(1)
