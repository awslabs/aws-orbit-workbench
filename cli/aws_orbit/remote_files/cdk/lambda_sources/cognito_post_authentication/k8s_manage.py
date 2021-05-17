import logging
import os
import sys
import subprocess
from typing import Any, Dict, List, Optional

import boto3
from kubernetes import config, client
from kubernetes.client.rest import ApiException

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
    user_name = event.get("user_name")
    user_email = event.get("user_email")
    user_pool_id = event.get("user_pool_id")
    expected_user_namespaces = event.get('expected_user_namespaces')

    create_kubeconfig()

    api = client.CoreV1Api()

    manage_user_namespace(kubernetes_api_client=api, expected_user_namespaces=expected_user_namespaces, user_name=user_name, user_email=user_email, user_pool_id=user_pool_id)

def run_command(cmd: str) -> str:
    """ Module to run shell commands. """
    cmds = cmd.split(" ")
    try:
        output = subprocess.run(cmds, stderr=subprocess.STDOUT, shell=False, timeout=120, universal_newlines=True)
        print(output)
    except subprocess.CalledProcessError as exc:
        # print("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output.decode("utf-8")))
        raise exc
    return output

def create_kubeconfig() -> bool:
    KUBECONFIG_PATH = "/tmp/.kubeconfig"
    orbit_env = os.environ.get('ORBIT_ENV')
    account_id = os.environ.get('ACCOUNT_ID')

    logger.info(f'Generating kubeconfig in {KUBECONFIG_PATH}')
    run_command(f"aws eks update-kubeconfig --name orbit-{orbit_env} --role-arn arn:aws:iam::{account_id}:role/orbit-{orbit_env}-admin --kubeconfig {KUBECONFIG_PATH}")
    
    logger.info("Loading kubeconfig")
    try:
        config.load_kube_config(KUBECONFIG_PATH)
        logger.info("Loaded kubeconfig successfully")
    except config.ConfigException:
        raise Exception("Could not configure kubernetes python client")

def manage_user_namespace(kubernetes_api_client: client.CoreV1Api, expected_user_namespaces: List, user_name: str, user_email: str, user_pool_id: str) -> None:
    api = kubernetes_api_client

    all_ns_raw = api.list_namespace().to_dict()
    all_ns = [item.get('metadata').get('name') for item in all_ns_raw['items']  if item.get('metadata').get('name').startswith(user_name)]

    # Create user namespace
    for team, user_ns in expected_user_namespaces.items():
        if user_ns not in all_ns:
            logger.info(f'User namespace {user_ns} doesnt exist. Creating...')
            name = user_ns
            annotations = {"owner": user_email}
            labels = {
                "orbit/space": "user",
                "orbit/team": team,
                "orbit/env": os.environ.get('ORBIT_ENV'),
                "orbit/user": user_name,
                "istio-injection": "enabled"
            }

            body = client.V1Namespace()
            body.metadata = client.V1ObjectMeta(name=name, annotations=annotations, labels=labels)

            try:
                api.create_namespace(body=body)
                logger.info(f"Created namespace {name}")
            except ApiException as e:
                logger.info(f"Exception when trying to create user namespace {name}")

    logger.info([item.get('metadata').get('name') for item in api.list_namespace().to_dict()['items']])

    # Remove user namespace
    for user_ns in all_ns:
        if user_ns not in expected_user_namespaces.values():
            logger.info(f'User {user_name} is not expected to be part of the {user_ns} namespace. Removing...')

            try:
                api.delete_namespace(name=user_ns)
                logger.info(f"Removed namespace {user_ns}")
            except ApiException as e:
                logger.info("Exception when trying to remove user namespace {user_ns}")

    