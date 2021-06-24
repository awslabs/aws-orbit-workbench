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
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dump_resource, dynamic_client, logger, pod_default
from urllib3.exceptions import ReadTimeoutError


def _verbosity() -> int:
    try:
        return int(os.environ.get("ORBIT_CONTROLLER_LOG_VERBOSITY", "0"))
    except Exception:
        return 0


def process_added_event(pod_setting: Dict[str, Any]) -> None:
    name = pod_setting["metadata"]["name"]
    namespace = pod_setting["metadata"]["namespace"]
    owner_uid = pod_setting["metadata"]["uid"]
    desc = pod_setting["spec"].get("desc", "")
    client = dynamic_client()

    try:
        pod_default.create_pod_default(
            namespace=namespace,
            pod_default=pod_default.construct(
                name=name,
                desc=desc,
                owner_reference={
                    "apiVersion": f"{ORBIT_API_GROUP}/{ORBIT_API_VERSION}",
                    "kind": "PodSetting",
                    "name": name,
                    "uid": owner_uid,
                },
                labels={"orbit/space": "team", "orbit/team": namespace},
            ),
            client=client,
        )
        logger.debug("ADDED pod_default for pod_setting: %s", dump_resource(pod_setting))
    except Exception:
        if _verbosity() > 0:
            logger.exception(
                "IGNORING ERROR ADDING pod_default for pod_setting: %s",
                dump_resource(pod_setting),
            )
        else:
            logger.error(
                "IGNORING ERROR ADDING pod_default for pod_setting: %s",
                dump_resource(pod_setting),
            )


def process_modified_event(pod_setting: Dict[str, Any]) -> None:
    name = pod_setting["metadata"]["name"]
    namespace = pod_setting["metadata"]["namespace"]
    desc = pod_setting["spec"].get("desc", "")
    client = dynamic_client()

    try:
        pod_default.modify_pod_default(namespace=namespace, name=name, desc=desc, client=client)
        logger.debug("MODIFIED pod_default for pod_setting: %s", dump_resource(pod_setting))
    except Exception:
        if _verbosity() > 0:
            logger.exception(
                "IGNORING ERROR MODIFIYING pod_default for pod_setting: %s",
                dump_resource(pod_setting),
            )
        else:
            logger.error(
                "IGNORING ERROR MODIFIYING pod_default for pod_setting: %s",
                dump_resource(pod_setting),
            )


def process_deleted_event(pod_setting: Dict[str, Any]) -> None:
    name = pod_setting["metadata"]["name"]
    namespace = pod_setting["metadata"]["namespace"]
    client = dynamic_client()

    try:
        pod_default.delete_pod_default(namespace=namespace, name=name, client=client)
        logger.debug("DELETED pod_default for pod_setting: %s", dump_resource(pod_setting))
    except Exception:
        if _verbosity() > 0:
            logger.exception(
                "IGNORING ERROR DELETING pod_default for pod_setting: %s",
                dump_resource(pod_setting),
            )
        else:
            logger.error(
                "IGNORING ERROR DELETING pod_default for pod_setting: %s",
                dump_resource(pod_setting),
            )


def watch(queue: Queue, state: Dict[str, Any]) -> int:  # type: ignore
    while True:
        try:
            client = dynamic_client()
            api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="PodSetting")

            logger.info("Monitoring PodSettings")

            kwargs = {}
            resource_version = state.get("lastResourceVersion", 0)
            if resource_version >= 0:
                kwargs["resource_version"] = resource_version

            for event in api.watch(**kwargs):
                if _verbosity() > 2:
                    logger.debug("event object: %s", event)
                pod_setting = event["raw_object"]
                state["lastResourceVersion"] = pod_setting.get("metadata", {}).get("resourceVersion", 0)
                logger.debug("watcher state: %s", state)
                queue_event = {"type": event["type"], "raw_object": event["raw_object"]}

                labels = event["raw_object"].get("metadata", {}).get("labels", {})
                if labels.get("orbit/space") == "team" and "orbit/disable-watcher" not in labels:
                    logger.debug(
                        "Queueing PodSetting event for processing type: %s pod_setting: %s",
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
                state["lastResourceVersion"] = -1
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


def process_pod_settings(queue: Queue, state: Dict[str, Any], replicator_id: int) -> int:  # type: ignore
    logger.info("Started PodSetting Processor Id: %s", replicator_id)
    pod_setting_event: Optional[Dict[str, Any]] = None

    while True:
        try:
            pod_setting_event = cast(Dict[str, Any], queue.get(block=True, timeout=None))

            if pod_setting_event["type"] == "ADDED":
                process_added_event(pod_setting=pod_setting_event["raw_object"])
            elif pod_setting_event["type"] == "MODIFIED":
                process_modified_event(pod_setting=pod_setting_event["raw_object"])
            # elif pod_setting_event["type"] == "DELETED":
            #     process_deleted_event(pod_setting=pod_setting_event["raw_object"])
            else:
                logger.debug("Skipping PodSetting event: %s", dump_resource(pod_setting_event))
        except Exception:
            logger.exception(
                "Failed to process PodSetting event: %s",
                dump_resource(pod_setting_event),
            )
        finally:
            pod_setting_event = None
            time.sleep(1)
