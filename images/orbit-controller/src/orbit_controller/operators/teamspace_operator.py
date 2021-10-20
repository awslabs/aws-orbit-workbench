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

import json
import logging
import os
from typing import Any

import kopf
from kubernetes import dynamic
from kubernetes.client import ApiException, CoreV1Api, CustomObjectsApi, V1DeleteOptions, api_client
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION


def _dynamic_client() -> dynamic.DynamicClient:
    return dynamic.DynamicClient(client=api_client.ApiClient())


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, logger: kopf.Logger, **_: Any) -> None:
    settings.persistence.progress_storage = kopf.MultiProgressStorage(
        [
            kopf.AnnotationsProgressStorage(prefix="orbit.aws"),
            kopf.StatusProgressStorage(field="status.orbit-aws"),
        ]
    )
    settings.posting.level = logging.INFO
    settings.persistence.finalizer = "teamspace-operator.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))
    logger.info("START the Teamspace Controller")


@kopf.on.resume(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "teamspaces",
    field="status.teamspaceOperator.status",
    value=kopf.ABSENT,
)
@kopf.on.create(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "teamspaces",
    field="status.teamspaceOperator.status",
    value=kopf.ABSENT,
)
def install_team(patch: kopf.Patch, logger: kopf.Logger, **_: Any) -> str:
    logger.info("In INSTALL_TEAM  Teamspace Controller")
    patch["status"] = {"teamspaceOperator": {"status": "Installed"}}
    return "Installed"


@kopf.on.delete(ORBIT_API_GROUP, ORBIT_API_VERSION, "teamspaces")  # type: ignore
def uninstall_team(namespace: str, name: str, spec: kopf.Spec, patch: kopf.Patch, logger: kopf.Logger, **_: Any) -> str:
    logger.info("In UNINSTALL_TEAM  Teamspace Controller")

    # spec:
    # env: ${env_name}
    # space: team
    # team: ${team}
    team_spec = spec.get("team", None)
    logger.info(f"Preparing to Destroy all resources in team namespace {namespace}")
    if team_spec:
        _remove_team_resources(namespace=namespace, team_spec=team_spec, logger=logger)
        _remove_user_namespaces(namespace=namespace, team_spec=team_spec, logger=logger)
        patch["status"] = {"teamspaceOperator": {"status": "DeleteProcessed"}}
    else:
        logging.warn("Team spec not found...moving on")
    return "Uninstalled"


def _remove_user_namespaces(namespace: str, team_spec: str, logger: kopf.Logger, **_: Any):  # type: ignore
    logger.info(
        f"Removing all user namespaces with labels orbit/team={team_spec},orbit/space=user in namespace {namespace} "
    )

    v1 = CoreV1Api()
    label_selector = f"orbit/team={team_spec},orbit/space=user"
    all_namespaces = v1.list_namespace(label_selector=label_selector).to_dict()

    all_ns = [
        item.get("metadata").get("name") for item in all_namespaces["items"] if item.get("metadata", {}).get("name")
    ]
    for ns in all_ns:
        logger.info(f"Calling delete namespace {ns}")
        try:
            v1.delete_namespace(name=ns, async_req=True)
        except ApiException as e:
            logger.warn("calling CoreV1API->delete_namespace had an error: %s\n" % e)


def _remove_team_resources(namespace: str, team_spec: str, logger: kopf.Logger, **_: Any):  # type: ignore
    v1 = CoreV1Api()
    logger.info(f"_remove_team_resources looking with orbit/label={team_spec}")
    # Get all the namespaces with the team label
    label_selector = f"orbit/team={team_spec}"
    all_namespaces = v1.list_namespace(label_selector=label_selector).to_dict()
    all_ns = [
        item.get("metadata").get("name") for item in all_namespaces["items"] if item.get("metadata", {}).get("name")
    ]
    # List all the resources we want to force-delete:
    # group, version, plural, status_element
    custom_object_list = [
        ["sagemaker.aws.amazon.com", "v1", "hyperparametertuningjobs", "trainingJobStatus"],
        ["sagemaker.aws.amazon.com", "v1", "trainingjobs", "trainingJobStatus"],
        ["sagemaker.aws.amazon.com", "v1", "batchtransformjobs", "transformJobStatus"],
        ["sagemaker.aws.amazon.com", "v1", "hostingdeployments", "status"],
        ["kubeflow.org", "v1", "notebooks", "NA"],
        ["kubeflow.org", "v1", "profile", "NA"],
        ["batch", "v1", "jobs", "NA"],
        ["apps", "v1", "deployments", "NA"],
        ["apps", "v1", "statefulsets", "NA"],
    ]

    for namespace in all_ns:
        logger.info(f"Looking at NS {namespace}")

        for co in custom_object_list:
            _delete_custom_objects(group=co[0], version=co[1], plural=co[2], namespace=namespace, logger=logger)
        _delete_pods(namespace=namespace, logger=logger)

        for co in custom_object_list[0:4]:
            _patch_and_delete_stubborn_custom_resources(
                group=co[0], version=co[1], plural=co[2], status_element=co[3], namespace=namespace, logger=logger
            )


def _delete_pods(namespace: str, logger: kopf.Logger, use_async=True, **_: Any):  # type: ignore
    logger.info(f"Deleting ALL PODS in ns {namespace}")
    api = CoreV1Api()
    try:
        api.delete_collection_namespaced_pod(
            namespace=namespace,
            async_req=use_async,
            grace_period_seconds=0,
            propagation_policy="Background",
            body=V1DeleteOptions(),
        )
    except ApiException as e:
        logger.warn("calling CustomObjectsApi->delete_collection_namespaced_pod: %s\n" % e)


def _delete_custom_objects(  # type: ignore
    group: str, version: str, plural: str, namespace: str, logger: kopf.Logger, use_async=True, **_: Any
):

    logger.info(f"Deleting {plural}.{group} in ns {namespace}")
    co = CustomObjectsApi()

    try:
        resp = co.delete_collection_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=plural,
            grace_period_seconds=0,
            propagation_policy="Background",
            pretty="true",
            async_req=use_async,
            body=V1DeleteOptions(),
        )

        return resp
    except ApiException as e:
        logger.warn("calling CustomObjectsApi->delete_collection_namespaced_custom_object: %s\n" % e)
        logger.warn("Assume it did not exist")


def _patch_and_delete_stubborn_custom_resources(  # type: ignore
    group: str,
    version: str,
    plural: str,
    namespace: str,
    status_element: str,
    logger: kopf.Logger,
    use_async=True,
    **_: Any,
):
    logger.info(f"_patch_and_delete_stubborn_custom_resources for {plural}.{group} in namespace {namespace}")
    co = CustomObjectsApi()
    resp = co.list_namespaced_custom_object(group=group, version=version, plural=plural, namespace=namespace)
    failed_res = [
        item.get("metadata").get("name")
        for item in resp["items"]
        if item.get("status", {}).get(status_element) in ["Failed", "Completed", "InProgress"]
    ]
    for item in failed_res:
        try:
            logger.info(f"Patching item {item} in {plural}.{group}")
            patch = json.loads("""{"metadata":{"finalizers":[]}}""")
            co.patch_namespaced_custom_object(
                group=group, version=version, plural=plural, namespace=namespace, name=item, body=patch
            )
            logger.info(f"Deleting item {item} in {plural}.{group}")
            co.delete_namespaced_custom_object(
                group=group,
                version=version,
                plural=plural,
                namespace=namespace,
                name=item,
            )
        except ApiException as e:
            logger.error("Trying to patch and delete failed: %s\n" % e)
