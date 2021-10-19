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

from typing import Any, Dict, List, Optional

import kopf
from kubernetes import dynamic
from kubernetes.client.rest import ApiException
from kubernetes.dynamic.client import DynamicClient

KUBEFLOW_API_GROUP = "kubeflow.org"
KUBEFLOW_API_VERSION = "v1alpha1"


def construct(
    name: str,
    desc: str,
    owner_reference: Optional[Dict[str, str]] = None,
    labels: Optional[Dict[str, str]] = None,
    annnotations: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    poddefault: Dict[str, Any] = {
        "apiVersion": f"{KUBEFLOW_API_GROUP}/{KUBEFLOW_API_VERSION}",
        "kind": "PodDefault",
        "metadata": {
            "name": name,
            "labels": labels,
            "annotations": annnotations,
        },
        "spec": {"selector": {"matchLabels": {f"orbit/{name}": ""}}, "desc": desc},
    }
    if owner_reference is not None:
        poddefault["metadata"]["ownerReferences"] = [owner_reference]
    return poddefault


def create_poddefault(
    namespace: str,
    poddefault: Dict[str, Any],
    client: dynamic.DynamicClient,
    logger: kopf.Logger,
) -> None:
    api = client.resources.get(api_version=KUBEFLOW_API_VERSION, group=KUBEFLOW_API_GROUP, kind="PodDefault")
    api.create(namespace=namespace, body=poddefault)
    logger.debug(
        "Created PodDefault: %s in Namespace: %s",
        poddefault["metadata"]["name"],
        namespace,
    )


def modify_poddefault(
    namespace: str,
    name: str,
    desc: str,
    client: dynamic.DynamicClient,
    logger: kopf.Logger,
) -> None:
    api = client.resources.get(api_version=KUBEFLOW_API_VERSION, group=KUBEFLOW_API_GROUP, kind="PodDefault")
    patch = {"spec": {"desc": desc}}
    api.patch(namespace=namespace, name=name, body=patch)
    logger.debug("Modified PodDefault: %s in Namespace: %s", name, namespace)


def delete_poddefault(namespace: str, name: str, client: dynamic.DynamicClient, logger: kopf.Logger) -> None:
    api = client.resources.get(api_version=KUBEFLOW_API_VERSION, group=KUBEFLOW_API_GROUP, kind="PodDefault")
    api.delete(namespace=namespace, name=name, body={})
    logger.debug("Deleted PodDefault: %s in Namesapce: %s", name, namespace)


def copy_poddefaults_to_user_namespaces(
    poddefaults: List[Dict[str, Any]],
    user_namespaces: List[str],
    client: DynamicClient,
    logger: kopf.Logger,
) -> None:
    logger.debug(
        "Copying PodDefaults %s to user Namespaces %s",
        [pd["metadata"]["name"] for pd in poddefaults],
        user_namespaces,
    )
    for poddefault in poddefaults:
        for namespace in user_namespaces:
            try:
                kwargs = {
                    "name": poddefault["metadata"]["name"],
                    "desc": poddefault["spec"]["desc"],
                    "labels": {
                        "orbit/space": "user",
                        "orbit/team": poddefault["metadata"]["labels"].get("orbit/team", None),
                    },
                }
                create_poddefault(
                    namespace=namespace,
                    poddefault=construct(**kwargs),
                    client=client,
                    logger=logger,
                )
            except ApiException as e:
                logger.warn(
                    "Unable to create PodDefault %s in Namespace %s: %s",
                    poddefault["metadata"]["name"],
                    namespace,
                    str(e.body),
                )
            except Exception as e:
                logger.error(
                    "Failed to create PodDefault",
                    str(e),
                )


def modify_poddefaults_in_user_namespaces(
    poddefaults: List[Dict[str, Any]],
    user_namespaces: List[str],
    client: DynamicClient,
    logger: kopf.Logger,
) -> None:
    logger.debug(
        "Modifying PodDefaults %s in user Namespaces %s",
        [pd["metadata"]["name"] for pd in poddefaults],
        user_namespaces,
    )
    for poddefault in poddefaults:
        for namespace in user_namespaces:
            try:
                modify_poddefault(
                    namespace=namespace,
                    name=poddefault["metadata"]["name"],
                    desc=poddefault["spec"]["desc"],
                    client=client,
                    logger=logger,
                )
            except Exception as e:
                logger.warn(
                    "Unable to delete PodDefault %s from Namespace %s: %s",
                    poddefault["metadata"]["name"],
                    namespace,
                    str(e),
                )


def delete_poddefaults_from_user_namespaces(
    poddefaults: List[Dict[str, Any]],
    user_namespaces: List[str],
    client: DynamicClient,
    logger: kopf.Logger,
) -> None:
    logger.debug(
        "Deleting PodDefaults %s from user Namespaces %s",
        [pd["metadata"]["name"] for pd in poddefaults],
        user_namespaces,
    )
    for poddefault in poddefaults:
        for namespace in user_namespaces:
            try:
                delete_poddefault(
                    namespace=namespace,
                    name=poddefault["metadata"]["name"],
                    client=client,
                    logger=logger,
                )
            except Exception as e:
                logger.warn(
                    "Unable to delete PodDefault %s from Namespace %s: %s",
                    poddefault["metadata"]["name"],
                    namespace,
                    str(e),
                )
