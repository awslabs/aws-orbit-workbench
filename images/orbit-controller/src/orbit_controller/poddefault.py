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
from typing import Any, Dict, List, Optional, cast

from kubernetes import dynamic
from kubernetes.dynamic import exceptions as k8s_exceptions
from kubernetes.dynamic.client import DynamicClient
from orbit_controller import dump_resource, dynamic_client, logger
from urllib3.exceptions import ReadTimeoutError

KUBEFLOW_API_GROUP = "kubeflow.org"
KUBEFLOW_API_VERSION = "v1alpha1"


def _verbosity() -> int:
    try:
        return int(os.environ.get("ORBIT_CONTROLLER_LOG_VERBOSITY", "0"))
    except Exception:
        return 0


def _get_user_namespaces(client: dynamic.DynamicClient, team: str) -> List[Dict[str, Any]]:
    api = client.resources.get(api_version="v1", kind="Namespace")

    namespaces = api.get(label_selector=f"orbit/space=user,orbit/team={team}")
    return cast(List[Dict[str, Any]], namespaces.to_dict().get("items", []))


def get_team_poddefaults(client: dynamic.DynamicClient, team: str) -> List[Dict[str, Any]]:
    api = client.resources.get(api_version=KUBEFLOW_API_VERSION, group=KUBEFLOW_API_GROUP, kind="PodDefault")

    poddefaults = api.get(label_selector=f"orbit/space=team,orbit/team={team}")
    return cast(List[Dict[str, Any]], poddefaults.to_dict().get("items", []))


def construct(
    name: str,
    desc: str,
    owner_reference: Dict[str, str],
    labels: Optional[Dict[str, str]] = None,
    annnotations: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return {
        "apiVersion": f"{KUBEFLOW_API_GROUP}/{KUBEFLOW_API_VERSION}",
        "kind": "PodDefault",
        "metadata": {
            "name": name,
            "labels": labels,
            "annotations": annnotations,
            "owner_references": [owner_reference],
        },
        "spec": {"selector": {"matchLabels": {f"orbit/{name}": ""}}, "desc": desc},
    }


def create_poddefault(namespace: str, poddefault: Dict[str, Any], client: dynamic.DynamicClient) -> None:
    api = client.resources.get(api_version=KUBEFLOW_API_VERSION, group=KUBEFLOW_API_GROUP, kind="PodDefault")
    api.create(namespace=namespace, body=poddefault)
    logger.debug("Created poddefault: %s", dump_resource(poddefault))


def modify_poddefault(namespace: str, name: str, desc: str, client: dynamic.DynamicClient) -> None:
    api = client.resources.get(api_version=KUBEFLOW_API_VERSION, group=KUBEFLOW_API_GROUP, kind="PodDefault")
    patch = {"spec": {"desc": desc}}
    api.patch(namespace=namespace, name=name, body=patch)
    logger.debug("Modified poddefault: %s in namespace: %s", name, namespace)


def delete_poddefault(namespace: str, name: str, client: dynamic.DynamicClient) -> None:
    api = client.resources.get(api_version=KUBEFLOW_API_VERSION, group=KUBEFLOW_API_GROUP, kind="PodDefault")
    api.delete(namespace=namespace, name=name, body={})
    logger.debug("Deleted poddefault: %s in namesapce: %s", name, namespace)


def copy_poddefaults_to_user_namespaces(
    poddefaults: List[Dict[str, Any]], user_namespaces: List[str], client: DynamicClient
) -> None:
    logger.debug("Copying poddefaults to user namespaces: %s, %s", dump_resource(poddefaults), user_namespaces)
    for poddefault in poddefaults:
        for namespace in user_namespaces:
            kwargs = {
                "name": poddefault["metadata"]["name"],
                "desc": poddefault["spec"]["desc"],
                "labels": {"orbit/space": "user", "orbit/team": poddefault["metadata"]["labels"].get("team", None)},
                "owner_references": [
                    {
                        "apiVersion": f"{KUBEFLOW_API_GROUP}/{KUBEFLOW_API_VERSION}",
                        "kind": "PodDefault",
                        "name": poddefault["metadata"]["name"],
                        "uid": poddefault["metadata"]["uid"],
                    }
                ],
            }
            create_poddefault(namespace=namespace, poddefault=construct(**kwargs), client=client)


def process_added_event(poddefault: Dict[str, Any]) -> None:
    client = dynamic_client()
    labels = poddefault.get("metadata", {}).get("labels", {})

    if labels.get("orbit/space", None) != "team":
        logger.debug("Skipping ADD processing, non-teamspace PodDefault: %s", dump_resource(poddefault))
        return

    team = labels.get("orbit/team", None)
    if not team:
        logger.error("Skipping ADD processing, unable to determine Team: %s", dump_resource(poddefault))

    user_namespaces = [item["metadata"]["name"] for item in _get_user_namespaces(client=client, team=team)]
    copy_poddefaults_to_user_namespaces(poddefaults=[poddefault], user_namespaces=user_namespaces, client=client)


def process_modified_event(poddefault: Dict[str, Any]) -> None:
    client = dynamic_client()
    labels = poddefault.get("metadata", {}).get("labels", {})

    if labels.get("orbit/space", None) != "team":
        logger.debug("Skipping MODIFY processing, non-teamspace PodDefault: %s", dump_resource(poddefault))
        return

    team = labels.get("orbit/team", None)
    if not team:
        logger.error("Skipping MODIFY processing, unable to determine Team: %s", dump_resource(poddefault))

    user_namespaces = [item["metadata"]["name"] for item in _get_user_namespaces(client=client, team=team)]
    for namespace in user_namespaces:
        modify_poddefault(
            namespace=namespace, name=poddefault["metadata"]["name"], desc=poddefault["spec"]["desc"], client=client
        )


def process_deleted_event(poddefault: Dict[str, Any]) -> None:
    logger.debug("Skipping DELETE processing")


def watch(queue: Queue, state: Dict[str, Any]) -> int:  # type: ignore
    while True:
        try:
            client = dynamic_client()
            api = client.resources.get(
                api_version=KUBEFLOW_API_VERSION,
                group=KUBEFLOW_API_GROUP,
                kind="PodDefault",
            )

            logger.info("Monitoring PodDefaults")

            kwargs = {
                "resource_version": state.get("lastResourceVersion", 0),
                "label_selector": "orbit/space=team",
            }
            for event in api.watch(**kwargs):
                if _verbosity() > 2:
                    logger.debug("event object: %s", event)
                poddefault = event["raw_object"]
                state["lastResourceVersion"] = poddefault.get("metadata", {}).get("resourceVersion", 0)
                logger.debug("watcher state: %s", state)
                queue_event = {"type": event["type"], "raw_object": event["raw_object"]}
                logger.debug(
                    "Queueing PodDefault event for processing type: %s poddefault: %s",
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
                logger.exception("Unknown ApiException in PodDefaultWatcher. Failing")
                raise
        except Exception:
            logger.exception("Unknown error in PodDefaultWatcher. Failing")
            raise
        else:
            logger.warning(
                "Watch died gracefully, starting back up with last_resource_version: %s",
                state["lastResourceVersion"],
            )


def process_poddefaults(queue: Queue, state: Dict[str, Any], replicator_id: int) -> int:  # type: ignore
    logger.info("Started PodDefault Processor Id: %s", replicator_id)
    poddefault_event: Optional[Dict[str, Any]] = None

    while True:
        try:
            poddefault_event = cast(Dict[str, Any], queue.get(block=True, timeout=None))

            if poddefault_event["type"] == "ADDED":
                process_added_event(poddefault=poddefault_event["raw_object"])
            elif poddefault_event["type"] == "MODIFIED":
                process_modified_event(poddefault=poddefault_event["raw_object"])
            elif poddefault_event["type"] == "DELETED":
                process_deleted_event(poddefault=poddefault_event["raw_object"])
            else:
                logger.debug("Skipping PodDefault event: %s", dump_resource(poddefault_event))
        except Exception:
            logger.exception(
                "Failed to process PodDefault event: %s",
                dump_resource(poddefault_event),
            )
        finally:
            poddefault_event = None
            time.sleep(1)
