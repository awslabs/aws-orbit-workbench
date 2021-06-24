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

import base64
import copy
import logging
import os
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, cast

import jsonpatch
import jsonpath_ng
from flask import jsonify
from kubernetes import dynamic
from kubernetes.dynamic import exceptions as k8s_exceptions
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dump_resource, dynamic_client, get_module_state
from orbit_controller.image_replication import create_image_replication
from orbit_controller.image_replication import get_config as get_image_replication_config
from orbit_controller.image_replication import get_desired_image

ORBIT_POD_SETTINGS_CACHE = None
ORBIT_POD_SETTINGS_STATE = None


def _verbosity() -> int:
    try:
        return int(os.environ.get("ORBIT_CONTROLLER_LOG_VERBOSITY", "0"))
    except Exception:
        return 0


def get_pod_settings(logger: logging.Logger, client: dynamic.DynamicClient) -> List[Dict[str, Any]]:
    global ORBIT_POD_SETTINGS_CACHE
    global ORBIT_POD_SETTINGS_STATE

    state_copy = deepcopy(get_module_state(module="podsettingsWatcher"))
    logger.debug(
        "pod_settingsWatcher States Previous: %s Current: %s",
        state_copy,
        ORBIT_POD_SETTINGS_STATE,
    )
    if state_copy != ORBIT_POD_SETTINGS_STATE:
        logger.debug("Updating pod_settings cache")
        api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="PodSetting")
        pod_settings = api.get()
        ORBIT_POD_SETTINGS_CACHE = pod_settings.to_dict().get("items", [])
    ORBIT_POD_SETTINGS_STATE = state_copy
    return cast(List[Dict[str, Any]], ORBIT_POD_SETTINGS_CACHE)


def get_namespace(client: dynamic.DynamicClient, name: str) -> Optional[Dict[str, Any]]:
    api = client.resources.get(api_version="v1", kind="Namespace")

    try:
        return cast(Dict[str, Any], api.get(name=name).to_dict())
    except k8s_exceptions.NotFoundError:
        return None


def filter_pod_settings(
    logger: logging.Logger,
    pod_settings: List[Dict[str, Any]],
    namespace: str,
    pod: Dict[str, Any],
) -> List[Dict[str, Any]]:
    filtered_pod_settings: List[Dict[str, Any]] = []

    def labels_match(labels: Dict[str, str], selector_labels: Dict[str, str]) -> bool:
        for key, value in selector_labels.items():
            label_value = labels.get(key, None)
            if label_value != value:
                logger.debug(
                    "NoHit: Label value check, label %s with value %s does not equal %s",
                    key,
                    label_value,
                    value,
                )
                return False
        return True

    def expressions_match(labels: Dict[str, str], selector_expressions: List[Dict[str, Any]]) -> bool:
        for match_expression in selector_expressions:
            pod_label_value = labels.get(match_expression["key"], None)
            operator = match_expression["operator"]
            values = match_expression.get("values", [])

            if operator == "Exists" and pod_label_value is None:
                logger.debug(
                    "NoHit: Exists check, label %s does not exist",
                    match_expression["key"],
                )
                return False
            if operator == "NotExists" and pod_label_value is not None:
                logger.debug(
                    "NoHit: NotExists check, label %s does exist with value %s",
                    match_expression["key"],
                    pod_label_value,
                )
                return False
            if operator == "In" and pod_label_value not in values:
                logger.debug(
                    "NoHit: In check, label %s has value %s which is not in %s",
                    match_expression["key"],
                    pod_label_value,
                    values,
                )
                return False
            if operator == "NotIn" and pod_label_value in values:
                logger.debug(
                    "NoHit: NotIn check, label %s has value %s which is in %s",
                    match_expression["key"],
                    pod_label_value,
                    values,
                )
                return False
        return True

    for pod_setting in pod_settings:
        if pod_setting["metadata"]["namespace"] != namespace:
            logger.debug(
                "NoHit: PodSetting namespace check. Namespace: %s PodSetting: %s",
                namespace,
                dump_resource(pod_setting),
            )
            continue

        pod_labels = pod["metadata"].get("labels", {})
        selector_labels = pod_setting["spec"]["podSelector"].get("matchLabels", {})
        selector_expressions = pod_setting["spec"]["podSelector"].get("matchExpressions", [])

        if pod_labels == {}:
            logger.debug("NoHit: Pod contains no labels to match against: %s", dump_resource(pod))
            continue
        elif selector_labels == {} and selector_expressions == []:
            logger.debug(
                "NoHit: PodSetting contains no podSelectors to match against: %s",
                dump_resource(pod_setting),
            )
            continue
        elif not labels_match(pod_labels, selector_labels):
            logger.debug(
                "NoHit: Pod labels and PodSetting matchLabels do not match. Pod: %s PodSetting: %s",
                dump_resource(pod),
                dump_resource(pod_setting),
            )
            continue
        elif not expressions_match(pod_labels, selector_expressions):
            logger.debug(
                "NoHit: Pod labels and PodSetting matchExpressions do not match. Pod: %s PodSetting: %s",
                dump_resource(pod),
                dump_resource(pod_setting),
            )
            continue
        else:
            logger.debug(
                "Hit: Pod labels and PodSetting podSelectors match. Pod: %s PodSetting: %s",
                dump_resource(pod),
                dump_resource(pod_setting),
            )
            filtered_pod_settings.append(pod_setting)
    return filtered_pod_settings


def filter_pod_containers(
    containers: List[Dict[str, Any]],
    pod: Dict[str, Any],
    container_selector: Dict[str, str],
) -> List[Dict[str, Any]]:
    filtered_containers = []

    if "regex" in container_selector:
        container_selector_regex = (
            re.compile(r".*") if container_selector["regex"] == "*" else re.compile(container_selector["regex"])
        )
        filtered_containers.extend([c for c in containers if container_selector_regex.match(c.get("name", ""))])
    elif "jsonpath" in container_selector:
        container_selector_jsonpath = jsonpath_ng.parse(container_selector["jsonpath"])
        filtered_containers.extend(
            [
                c
                for c in containers
                if c.get("name", "") in [match.value for match in container_selector_jsonpath.find(pod)]
            ]
        )

    return filtered_containers


def apply_settings_to_pod(
    namespace: Dict[str, Any],
    pod_setting: Dict[str, Any],
    pod: Dict[str, Any],
    logger: logging.Logger,
) -> None:
    ps_spec = pod_setting["spec"]
    pod_spec = pod["spec"]

    # Merge
    if "serviceAccountName" in ps_spec:
        pod_spec["serviceAccountName"] = ps_spec.get("serviceAccountName", None)

    # Merge
    if "labels" in ps_spec:
        pod["metadata"]["labels"] = {
            **pod["metadata"].get("labels", {}),
            **ps_spec.get("labels", {}),
        }

    # Merge
    if "annotations" in ps_spec:
        pod["metadata"]["annotations"] = {
            **pod["metadata"].get("annotations", {}),
            **ps_spec.get("annotations", {}),
        }

    # Merge
    if "nodeSelector" in ps_spec:
        pod_spec["nodeSelector"] = {
            **pod_spec.get("nodeSelector", {}),
            **ps_spec.get("nodeSelector", {}),
        }

    # Merge
    if "securityContext" in ps_spec:
        pod_spec["securityContext"] = {
            **pod_spec.get("securityContext", {}),
            **ps_spec.get("securityContext", {}),
        }

    # Merge
    if "volumes" in ps_spec:
        # Filter out any existing volumes with names that match pod_setting volumes
        pod_spec["volumes"] = [
            pv
            for pv in pod_spec.get("volumes", [])
            if pv["name"] not in [psv["name"] for psv in ps_spec.get("volumes", [])]
        ]
        # Extend pod volumes with pod_setting volumes
        pod_spec["volumes"].extend(ps_spec.get("volumes", []))

    for container in filter_pod_containers(
        containers=pod_spec.get("initContainers", []),
        pod=pod_spec,
        container_selector=ps_spec.get("containerSelector", {}),
    ):
        apply_settings_to_container(namespace=namespace, pod_setting=pod_setting, pod=pod, container=container)
    for container in filter_pod_containers(
        containers=pod_spec.get("containers", []),
        pod=pod,
        container_selector=ps_spec.get("containerSelector", {}),
    ):
        apply_settings_to_container(namespace=namespace, pod_setting=pod_setting, pod=pod, container=container)
    logger.debug("modified pod: %s", dump_resource(pod))


def apply_settings_to_container(
    namespace: Dict[str, Any],
    pod_setting: Dict[str, Any],
    pod: Dict[str, Any],
    container: Dict[str, Any],
) -> None:
    ns_labels = namespace["metadata"].get("labels", {})
    ns_annotations = namespace["metadata"].get("annotations", {})
    ps_spec = pod_setting["spec"]

    # Drop any previous AWS_ORBIT_USER_SPACE or AWS_ORBIT_IMAGE env variables
    ps_spec["env"] = [e for e in ps_spec.get("env", []) if e["name"] not in ["AWS_ORBIT_USER_SPACE", "AWS_ORBIT_IMAGE"]]

    # Append new ones
    ps_spec["env"].extend(
        [
            {
                "name": "AWS_ORBIT_USER_SPACE",
                "value": namespace["metadata"].get("name", ""),
            },
            {"name": "AWS_ORBIT_IMAGE", "value": container.get("image", "")},
        ]
    )

    # Extend pod_setting ENV
    if "notebookApp" in ps_spec:
        # Drop any previous NB_PREFIX env variable
        ps_spec["env"] = [e for e in ps_spec.get("env", []) if e["name"] not in ["NB_PREFIX"]]
        ps_spec["env"].append(
            {
                "name": "NB_PREFIX",
                "value": f"/notebook/{pod.get('metadata', {}).get('namespace')}"
                f"/{pod.get('metadata', {}).get('labels', {}).get('notebook-name')}/{ps_spec['notebookApp']}",
            }
        )

    if ps_spec.get("injectUserContext", False):
        # Drop any previous USERNAME or USEREMAIL env variables
        ps_spec["env"] = [e for e in ps_spec.get("env", []) if e["name"] not in ["USERNAME", "USEREMAIL"]]
        # Append new ones
        ps_spec["env"].extend(
            [
                {
                    "name": "USERNAME",
                    "value": ns_labels.get("orbit/user", ns_labels.get("orbit/team", None)),
                },
                {"name": "USEREMAIL", "value": ns_annotations.get("owner", "")},
            ]
        )

    # Replace
    if "image" in ps_spec:
        container["image"] = ps_spec.get("image", None)

    # Replace
    if "imagePullPolicy" in ps_spec:
        container["imagePullPolicy"] = ps_spec.get("imagePullPolicy", None)

    # Merge
    if "lifecycle" in ps_spec:
        container["lifecycle"] = {
            **container.get("lifecycle", {}),
            **ps_spec.get("lifecycle", {}),
        }

    # Replace
    if "command" in ps_spec:
        container["command"] = ps_spec["command"]

    # Replace
    if "args" in ps_spec:
        container["args"] = ps_spec["args"]

    # Merge
    if "env" in ps_spec:
        # Filter out any existing env items with names that match pod_setting env items
        container["env"] = [
            pv for pv in container.get("env", []) if pv["name"] not in [psv["name"] for psv in ps_spec.get("env", [])]
        ]
        # Extend container env items with container pod_setting env items
        container["env"].extend(ps_spec.get("env", []))

    # Extend
    if "envFrom" in ps_spec:
        # Extend container envFrom with pod_setting envFrom
        container["envFrom"].extend(ps_spec.get("envFrom", []))

    # Merge
    if "volumeMounts" in ps_spec:
        # Filter out any existing volumes with names that match pod_setting volumes
        container["volumeMounts"] = [
            pv
            for pv in container.get("volumeMounts", [])
            if pv["name"] not in [psv["name"] for psv in ps_spec.get("volumeMounts", [])]
        ]
        # Extend container volumes with container volumes
        container["volumeMounts"].extend(ps_spec.get("volumeMounts", []))


def get_response(uid: str, patch: Optional[Dict[str, Any]] = None) -> str:
    response = {
        "allowed": True,
        "uid": uid,
    }
    if patch:
        response.update(
            {
                "patch": base64.b64encode(str(patch).encode()).decode(),
                "patchtype": "JSONPatch",
            }
        )

    return cast(str, jsonify({"response": response}))


def process_pod_setting_request(logger: logging.Logger, request: Dict[str, Any]) -> Any:
    if request.get("dryRun", False):
        logger.info("Dry run - Skip Pod Mutation")
        return get_response(uid=request["uid"])

    pod = request["object"]
    modified_pod = copy.deepcopy(pod)

    if _verbosity() > 2:
        logger.info("request: %s", request)

    client = dynamic_client()
    pod_settings = get_pod_settings(logger=logger, client=client)
    logger.debug("pod_settings: %s", dump_resource(pod_settings))

    namespace = get_namespace(client=client, name=request["namespace"])
    if namespace is None:
        logger.error("Fatal error, Namespace %s not found", name=request["namespace"])
        return get_response(uid=request["uid"])

    labels = namespace["metadata"].get("labels", {})
    team_namespace = labels.get("orbit/team", None)

    if team_namespace is None:
        logger.info("No orbit/team label found on namespace: %s", request["namespace"])
        return get_response(uid=request["uid"])

    team_pod_settings = filter_pod_settings(
        logger=logger,
        pod_settings=pod_settings,
        namespace=team_namespace,
        pod=pod,
    )
    logger.debug("filtered pod_settings: %s", dump_resource(team_pod_settings))

    try:
        for pod_setting in team_pod_settings:
            logger.debug("applying pod_setting: %s", dump_resource(pod_setting))
            apply_settings_to_pod(
                namespace=namespace,
                pod_setting=pod_setting,
                pod=modified_pod,
                logger=logger,
            )
    except Exception as e:
        logger.exception(e)
        pass

    patch = jsonpatch.JsonPatch.from_diff(pod, modified_pod)
    logger.info("patch: %s", str(patch).encode())
    return get_response(uid=request["uid"], patch=patch)


def process_image_replication_request(logger: logging.Logger, request: Dict[str, Any]) -> Any:
    if request.get("dryRun", False):
        logger.info("Dry run - Skip Pod Mutation")
        return get_response(uid=request["uid"])

    pod = request["object"]
    modified_pod = copy.deepcopy(pod)

    if _verbosity() > 2:
        logger.info("request: %s", request)

    pod_spec = modified_pod.get("spec", {})
    pod_annotations = modified_pod["metadata"].get("annotations", {})
    replications = {}

    for container in pod_spec.get("initContainers", []) + pod_spec.get("containers", []):
        image = container.get("image", "")
        desired_image = get_desired_image(config=get_image_replication_config(), image=image)
        if image != desired_image:
            container["image"] = desired_image
            replications[desired_image] = image
            pod_annotations[f"original-container-image/{container['name']}"] = image

    if replications != {}:
        client = dynamic_client()
        create_image_replication(namespace="orbit-system", images=replications, client=client)
        modified_pod["metadata"]["annotations"] = pod_annotations

    patch = jsonpatch.JsonPatch.from_diff(pod, modified_pod)
    logger.info("patch: %s", str(patch).encode())
    return get_response(uid=request["uid"], patch=patch)
