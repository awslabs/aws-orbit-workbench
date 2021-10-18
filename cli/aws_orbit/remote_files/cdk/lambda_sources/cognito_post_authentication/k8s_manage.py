import json
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, cast

import boto3
from kubernetes import client, config, dynamic
from kubernetes.client import api_client
from kubernetes.client.rest import ApiException


logger = logging.getLogger()
logger.setLevel(logging.INFO)

ORBIT_ENV = os.environ.get("ORBIT_ENV")
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")
REGION = os.environ.get("REGION")
ROLE_PREFIX = os.environ.get("ROLE_PREFIX")
ORBIT_API_VERSION = os.environ.get("ORBIT_API_VERSION", "v1")
ORBIT_API_GROUP = os.environ.get("ORBIT_API_GROUP", "orbit.aws")
ORBIT_SYSTEM_NAMESPACE = os.environ.get("ORBIT_SYSTEM_NAMESPACE", "orbit-system")
ORBIT_STATE_PATH = os.environ.get("ORBIT_STATE_PATH", "/state")
USERSPACE_CR_KIND = "UserSpace"
KUBECONFIG_PATH = "/tmp/.kubeconfig"

USERSPACE_DYNAMIC_CIENT = dynamic.DynamicClient(client=api_client.ApiClient()).resources.get(
        group=ORBIT_API_GROUP, api_version=ORBIT_API_VERSION, kind=USERSPACE_CR_KIND
    )

ssm = boto3.client("ssm")

context = ssm.get_parameter(Name=f"/orbit/{ORBIT_ENV}/context")
EFS_FS_ID = json.loads(context.get("Parameter").get("Value")).get("SharedEfsFsId")


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
    create_kubeconfig()

    api_CoreV1 = client.CoreV1Api()

    manage_user_namespace(event, api_CoreV1)


def run_command(cmd: str) -> None:
    """Module to run shell commands."""
    cmds = cmd.split(" ")
    try:
        output = subprocess.run(cmds, stderr=subprocess.STDOUT, shell=False, timeout=120, universal_newlines=True)
        print(output)
    except subprocess.CalledProcessError as exc:
        # print("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output.decode("utf-8")))
        raise exc


def create_kubeconfig() -> None:
    logger.info(f"Generating kubeconfig in {KUBECONFIG_PATH}")
    run_command(
        (
            "aws eks update-kubeconfig "
            f"--name orbit-{ORBIT_ENV} "
            f"--role-arn arn:aws:iam::{ACCOUNT_ID}:role{ROLE_PREFIX}orbit-{ORBIT_ENV}-{REGION}-admin "
            f"--kubeconfig {KUBECONFIG_PATH}"
        )
    )

    logger.info("Loading kubeconfig")
    try:
        config.load_kube_config(KUBECONFIG_PATH)
        logger.info("Loaded kubeconfig successfully")
    except config.ConfigException:
        raise Exception("Could not configure kubernetes python client")


def create_user_efs_endpoint(user: str, team_name: str) -> Dict[str, Any]:
    efs = boto3.client("efs")

    return cast(
        Dict[str, str],
        efs.create_access_point(
            FileSystemId=EFS_FS_ID,
            PosixUser={"Uid": 1000, "Gid": 100},
            RootDirectory={
                "Path": f"/{team_name}/private/{user}",
                "CreationInfo": {"OwnerUid": 1000, "OwnerGid": 100, "Permissions": "770"},
            },
            Tags=[{"Key": "TeamSpace", "Value": team_name}, {"Key": "Env", "Value": os.environ.get("ORBIT_ENV")}],
        ),
    )


def get_dynamic_client(cr_kind: str):
    api_dc = dynamic.DynamicClient(client=api_client.ApiClient()).resources.get(
        group=ORBIT_API_GROUP, api_version=ORBIT_API_VERSION, kind=cr_kind
    )
    return api_dc


def create_cr(
    cr_kind: str,
    name: str,
    env: str,
    space: str,
    team: str,
    user: str,
    user_efsapid: str,
    user_email: str,
    owner_reference: Optional[Dict[str, str]] = None,
    labels: Optional[Dict[str, str]] = None,
    annnotations: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    userspace: Dict[str, Any] = {
        "apiVersion": f"{ORBIT_API_GROUP}/{ORBIT_API_VERSION}",
        "kind": cr_kind,
        "metadata": {
            "name": name,
            "labels": labels,
            "annotations": annnotations,
            "namespace": name
        },
        "spec": {
            "env": env,
            "space": space,
            "team": team,
            "user": user,
            "userEfsApId": user_efsapid,
            "userEmail": user_email,
        },
    }
    if owner_reference is not None:
        userspace["metadata"]["ownerReferences"] = [owner_reference]

    userspace_cr = USERSPACE_DYNAMIC_CIENT.create(namespace=name, body=userspace).to_dict()

    return userspace_cr


def create_user_namespace(
    api: client.CoreV1Api,
    user_name: str,
    user_email: str,
    expected_user_namespaces: Dict[str, str],
    namespaces: List[str],
) -> None:
    for team, user_ns in expected_user_namespaces.items():
        try:
            team_namespace = api.read_namespace(name=team).to_dict()
            team_uid = team_namespace.get("metadata", {}).get("uid", None)
            logger.info(f"Retrieved Team Namespace uid: {team_uid}")
        except Exception:
            logger.exception("Error retrieving Team Namespace")
            team_uid = None
        if user_ns not in namespaces:
            logger.info(f"Creating EFS endpoint for {user_ns}...")
            resp = create_user_efs_endpoint(user=user_name, team_name=team)
            access_point_id = resp.get("AccessPointId")

            logger.info(f"User namespace {user_ns} doesnt exist. Creating...")
            kwargs = {
                "name": user_ns,
                "annotations": {"owner": user_email},
                "labels": {
                    "orbit/efs-access-point-id": access_point_id,
                    "orbit/efs-id": EFS_FS_ID,
                    "orbit/env": os.environ.get("ORBIT_ENV"),
                    "orbit/space": "user",
                    "orbit/team": team,
                    "orbit/user": user_name,
                    # "istio-injection": "enabled",
                },
            }
            if team_uid:
                kwargs["owner_references"] = [
                    client.V1OwnerReference(api_version="v1", kind="Namespace", name=team, uid=team_uid)
                ]

            body = client.V1Namespace()
            body.metadata = client.V1ObjectMeta(**kwargs)

            try:
                # create userspace namespace resource
                api.create_namespace(body=body)
                logger.info(f"Created namespace {user_ns}")
            except ApiException as ae:
                logger.error(f"Exception when trying to create user namespace {user_ns}")
                logger.error(ae.body)

            try:
                # create userspace custom resource for the given user namespace
                create_cr(
                    name=user_ns,
                    env=os.environ.get("ORBIT_ENV"),
                    space="user",
                    team=team,
                    user=user_name,
                    user_efsapid=access_point_id,
                    user_email=user_email,
                    owner_reference=kwargs["owner_references"],
                )
                logger.info(f"Created userspace custom resource {user_ns}")
            except Exception as ae:
                logger.error(f"Exception when trying to create userspace custom resource {user_ns}")
                logger.error(ae.body)


def delete_user_efs_endpoint(user_name: str, user_namespace: str, api: client.CoreV1Api) -> None:
    efs = boto3.client("efs")

    logger.info(f"Fetching the EFS access point in the namespace {user_namespace} for user {user_name}")

    try:
        user_namespace_info = api.read_namespace(name=user_namespace).to_dict()
        efs_access_point_id = user_namespace_info.get("metadata").get("labels").get("orbit/efs-access-point-id")
    except ApiException:
        logger.info(f"Exception when trying to read namespace {user_namespace}")

    logger.info(f"Deleting the EFS access point {efs_access_point_id} for user {user_name}")

    try:
        efs.delete_access_point(AccessPointId=efs_access_point_id)
        logger.info(f"Access point {efs_access_point_id} deleted")
    except efs.exceptions.AccessPointNotFound:
        logger.error(f"Access point not found: {efs_access_point_id}")
    except efs.exceptions.InternalServerError as e:
        logger.error(e)


def delete_user_namespace(
    api: client.CoreV1Api, user_name: str, expected_user_namespaces: Dict[str, str], namespaces: List[str]
) -> None:
    for user_ns in namespaces:
        if user_ns not in expected_user_namespaces.values():
            delete_user_profile(user_profile=user_ns)

            delete_user_efs_endpoint(user_name=user_name, user_namespace=user_ns, api=api)

            logger.info(f"User {user_name} is not expected to be part of the {user_ns} namespace. Removing...")
            try:
                USERSPACE_DYNAMIC_CIENT.delete(name=user_ns, namespace=user_ns)
                logger.info(f"Removed userspace custom resource {user_ns}")
            except Exception as ae:
                logger.error(f"Exception when trying to remove userspace custom resource {user_ns}")
                logger.error(ae.body)
            try:
                api.delete_collection_namespaced_pod(namespace=user_ns, grace_period_seconds=0)
                api.delete_namespace(name=user_ns)
                logger.info(f"Removed namespace {user_ns}")
            except ApiException as ae:
                logger.error(f"Exception when trying to remove user namespace {user_ns}")
                logger.error(ae.body)



def delete_user_profile(user_profile: str) -> None:
    logger.info(f"Removing profile {user_profile}")
    run_command(f"kubectl delete profile {user_profile} --kubeconfig {KUBECONFIG_PATH}")

    time.sleep(5)


def manage_user_namespace(event: Dict[str, Any], api: client.CoreV1Api) -> None:
    user_name = cast(str, event.get("user_name"))
    user_email = cast(str, event.get("user_email"))
    expected_user_namespaces = cast(Dict[str, str], event.get("expected_user_namespaces"))

    all_ns_raw = api.list_namespace().to_dict()
    all_ns = [
        item.get("metadata").get("name")
        for item in all_ns_raw["items"]
        if item.get("metadata", {}).get("name") and item.get("metadata", {}).get("name").endswith(user_name)
    ]

    create_user_namespace(
        api=api,
        user_name=user_name,
        user_email=user_email,
        expected_user_namespaces=expected_user_namespaces,
        namespaces=all_ns,
    )

    delete_user_namespace(
        api=api,
        user_name=user_name,
        expected_user_namespaces=expected_user_namespaces,
        namespaces=all_ns,
    )
