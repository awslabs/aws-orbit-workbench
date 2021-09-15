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
from typing import Any, Dict, List

import jsonpath_ng
import kopf


def filter_podsettings(
    podsettings: List[Dict[str, Any]],
    pod_labels: Dict[str, str],
    logger: kopf.Logger,
) -> List[Dict[str, Any]]:
    filtered_podsettings: List[Dict[str, Any]] = []

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

    for podsetting in podsettings:
        selector_labels = podsetting["spec"]["podSelector"].get("matchLabels", {})
        selector_expressions = podsetting["spec"]["podSelector"].get("matchExpressions", [])

        if pod_labels == {}:
            logger.debug("NoHit: Pod contains no labels to match against")
            continue
        elif selector_labels == {} and selector_expressions == []:
            logger.debug(
                "NoHit: PodSetting contains no podSelectors to match against. PodSetting: %s",
                podsetting["name"],
            )
            continue
        elif not labels_match(pod_labels, selector_labels):
            logger.debug(
                "NoHit: Pod labels and PodSetting matchLabels do not match. PodSetting: %s",
                podsetting["name"],
            )
            continue
        elif not expressions_match(pod_labels, selector_expressions):
            logger.debug(
                "NoHit: Pod labels and PodSetting matchExpressions do not match. PodSetting: %s",
                podsetting["name"],
            )
            continue
        else:
            logger.debug(
                "Hit: Pod labels and PodSetting podSelectors match. PodSetting: %s",
                podsetting["name"],
            )
            filtered_podsettings.append(podsetting)
    return filtered_podsettings


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
    podsetting: Dict[str, Any],
    pod: Dict[str, Any],
    logger: kopf.Logger,
) -> None:
    ps_spec = podsetting["spec"]
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
        # There exists a bug in some k8s client libs where a / in the key is interpretted as a path.
        # With annotations and labels, replacing / with ~1 like below works and ~1 is interpretted as
        # an escaped / char. This does not work here w/ the nodeSelector keys. Keys with a / are
        # interpretted as a jsonpath, and keys with ~1 are deemed invalid.
        # pod_spec["nodeSelector"] = {k.replace("/", "~1"): v for k, v in pod_spec["nodeSelector"].items()}

        # So instead, we strip out any path from the nodeSelector keys and use a multi-label approach
        # on our ManagedNodeGroups
        pod_spec["nodeSelector"] = {k.split("/")[-1]: v for k, v in pod_spec["nodeSelector"].items()}

    # Merge
    if "securityContext" in ps_spec:
        pod_spec["securityContext"] = {
            **pod_spec.get("securityContext", {}),
            **ps_spec.get("securityContext", {}),
        }

    # Merge
    if "volumes" in ps_spec:
        # Filter out any existing volumes with names that match podsetting volumes
        pod_spec["volumes"] = [
            pv
            for pv in pod_spec.get("volumes", [])
            if pv["name"] not in [psv["name"] for psv in ps_spec.get("volumes", [])]
        ]
        # Extend pod volumes with podsetting volumes
        pod_spec["volumes"].extend(ps_spec.get("volumes", []))

    # Merge
    for container in filter_pod_containers(
        containers=pod_spec.get("initContainers", []),
        pod=pod,
        container_selector=ps_spec.get("containerSelector", {}),
    ):
        apply_settings_to_container(namespace=namespace, podsetting=podsetting, pod=pod, container=container)
        logger.info(
            "Applied PodSetting %s to InitContainer %s",
            podsetting["name"],
            container["name"],
        )
    for container in filter_pod_containers(
        containers=pod_spec.get("containers", []),
        pod=pod,
        container_selector=ps_spec.get("containerSelector", {}),
    ):
        apply_settings_to_container(namespace=namespace, podsetting=podsetting, pod=pod, container=container)
        logger.info(
            "Applied PodSetting %s to Container %s",
            podsetting["name"],
            container["name"],
        )
    logger.info("Applied PodSetting %s to Pod", podsetting["name"])


def apply_settings_to_container(
    namespace: Dict[str, Any],
    podsetting: Dict[str, Any],
    pod: Dict[str, Any],
    container: Dict[str, Any],
) -> None:
    ns_labels = namespace.get("labels", {})
    ns_annotations = namespace.get("annotations", {})
    ps_spec = {k: v for k, v in podsetting["spec"].items()}

    # Drop any previous AWS_ORBIT_USER_SPACE or AWS_ORBIT_IMAGE env variables
    ps_spec["env"] = [e for e in ps_spec.get("env", []) if e["name"] not in ["AWS_ORBIT_USER_SPACE", "AWS_ORBIT_IMAGE"]]

    # Append new ones
    ps_spec["env"].extend(
        [
            {
                "name": "AWS_ORBIT_USER_SPACE",
                "value": namespace.get("name", ""),
            },
            {"name": "AWS_ORBIT_IMAGE", "value": container.get("image", "")},
        ]
    )

    # Extend podsetting ENV
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
        # Filter out any existing env items with names that match podsetting env items
        container["env"] = [
            pv for pv in container.get("env", []) if pv["name"] not in [psv["name"] for psv in ps_spec.get("env", [])]
        ]
        # Extend container env items with container podsetting env items
        container["env"].extend(ps_spec.get("env", []))

    # Extend
    if "envFrom" in ps_spec:
        # Extend container envFrom with podsetting envFrom
        container["envFrom"].extend(ps_spec.get("envFrom", []))

    # Merge
    if "volumeMounts" in ps_spec:
        # Filter out any existing volumes with names that match podsetting volumes
        container["volumeMounts"] = [
            pv
            for pv in container.get("volumeMounts", [])
            if pv["name"] not in [psv["name"] for psv in ps_spec.get("volumeMounts", [])]
        ]
        # Extend container volumes with container volumes
        container["volumeMounts"].extend(ps_spec.get("volumeMounts", []))

    if "resources" in ps_spec:
        if "resources" not in container:
            container["resources"] = {}

        if "limits" in ps_spec["resources"]:
            container["resources"]["limits"] = {
                **container["resources"].get("limits", {}),
                **ps_spec["resources"].get("limits", {}),
            }

        if "requests" in ps_spec["resources"]:
            container["resources"]["requests"] = {
                **container["resources"].get("requests", {}),
                **ps_spec["resources"].get("requests", {}),
            }
