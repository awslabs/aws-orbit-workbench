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
import time
from multiprocessing import Queue
from typing import Any, Dict, Optional, cast

from aws_orbit_admission_controller import load_config, logger, run_command
from kubernetes.client import CoreV1Api, V1ConfigMap
from kubernetes.watch import Watch
from urllib3.exceptions import ReadTimeoutError


def should_install_team_package(labels: Dict[str, str]) -> bool:
    return labels.get("orbit/space", None) != "team"


def process_removed_event(namespace: Dict[str, Any]) -> None:
    logger.debug("loading kubeconfig")
    load_config()
    namespace_name = namespace["metadata"]["name"]
    labels = namespace["metadata"].get("labels", {})
    annotations = namespace["metadata"].get("annotations", {})

    logger.info("processing removed namespace %s", namespace)
    space = labels.get("orbit/space", None)

    if space == 'team':
        logger.info("delete all namespaces that belong to the team %s", namespace_name)
        run_command(f"kubectl delete profile -l orbit/team={namespace_name}")
        time.sleep(60)
        run_command(f"kubectl delete namespace -l orbit/team={namespace_name}")
        logger.info("all namespaces that belong to the team %s are deleted", namespace_name)
    elif space == 'user':
        env = labels.get("orbit/env", None)
        team = labels.get("orbit/team", None)
        user = labels.get("orbit/user", None)
        user_email = annotations.get("owner", None)

        logger.debug("removed namespace: %s,%s,%s,%s", team, user, user_email, namespace_name)

        if not env or not space or not team or not user or not user_email:
            logger.error(
                "All of env, space, team, user, and user_email are required. Found: %s, %s, %s, %s, %s",
                env,
                space,
                team,
                user,
                user_email,
            )
            return

        team_context = get_team_context(team)
        helm_repo_url = team_context["HelmRepository"]
        helm_release = f"{namespace_name}-orbit-team"
        logger.debug("Adding Helm Repository: %s at %s", team, helm_repo_url)
        uninstall_chart(helm_release, team)

def process_added_event(namespace: Dict[str, Any]) -> None:
    logger.debug("loading kubeconfig")
    load_config()
    namespace_name = namespace["metadata"]["name"]
    labels = namespace["metadata"].get("labels", {})
    annotations = namespace["metadata"].get("annotations", {})

    logger.info("processing namespace")
    logger.debug("namespace: %s", namespace)

    if not should_install_team_package(namespace):
        return

    env = labels.get("orbit/env", None)
    space = labels.get("orbit/space", None)
    team = labels.get("orbit/team", None)
    user = labels.get("orbit/user", None)
    user_email = annotations.get("owner", None)
    user_efsapid = annotations.get("orbit/efs-access-point-id", None)

    logger.debug("new namespace: %s,%s,%s,%s", team, user, user_email, namespace_name)

    if not env or not space or not team or not user or not user_email:
        logger.error(
            "All of env, space, team, user, and user_email are required. Found: %s, %s, %s, %s, %s, %s",
            env,
            space,
            team,
            user,
            user_email,
            user_efsapid,
        )
        return

    team_context = get_team_context(team)
    helm_repo_url = team_context["HelmRepository"]
    logger.debug("Adding Helm Repository: %s at %s", team, helm_repo_url)
    helm_release = f"{namespace_name}-orbit-team"
    # add the team repo
    run_command(f"helm repo add {team} {helm_repo_url}")
    # install the helm package for this user space
    install_helm_chart(helm_release, namespace_name, team, user, user_email, user_efsapid)

    logger.info("Helm release %s installed at %s", helm_release, namespace_name)

def install_helm_chart(helm_release: str, namespace: str, team: str, user: str, user_email: str,
                       user_efsapid: str) -> None:
    cmd = (
        f"/usr/local/bin/helm upgrade --install --devel --debug --namespace {team} "
        f"{helm_release} {team}/user-space "
        f"--set user={user},user_email={user_email},namespace={namespace},user_efsapid={user_efsapid}"
    )

    logger.debug("running cmd: %s", cmd)
    output = run_command(cmd)
    logger.debug(output)
    logger.info("finished cmd: %s", cmd)


def uninstall_chart(helm_release: str, namespace: str) -> None:
    cmd = (
        f"/usr/local/bin/helm uninstall --debug --namespace {namespace} {helm_release}"
    )
    logger.debug("running uninstall cmd: %s", cmd)
    output = run_command(cmd)
    logger.debug(output)
    logger.info("finished uninstall cmd: %s", cmd)


def get_team_context(team: str) -> Dict[str, Any]:
    try:
        api_instance = CoreV1Api()
        team_context_cf: V1ConfigMap = api_instance.read_namespaced_config_map("orbit-team-context", team)
        team_context_str = team_context_cf.data["team"]

        logger.debug("team context: %s", team_context_str)
        team_context: Dict[str, Any] = json.loads(team_context_str)
        logger.debug("team context keys: %s", team_context.keys())
    except Exception as e:
        logger.error("Error during fetching team context configmap")
        raise e
    return team_context


def watch(queue: Queue, state: Dict[str, Any]) -> int:  # type: ignore
    while True:
        try:
            load_config()
            client = CoreV1Api()

            logger.info("Monitoring Namespaces")
            watcher = Watch()

            kwargs = {"label_selector": "orbit/space", "resource_version": state.get("lastResourceVersion", 0)}
            for event in watcher.stream(client.list_namespace, **kwargs):
                namespace = event["object"]
                state["lastResourceVersion"] = namespace.metadata.resource_version
                queue_event = {"type": event["type"], "raw_object": event["raw_object"]}
                logger.debug("Queueing Namespace event for processing: %s", queue_event)
                queue.put(queue_event)
        except ReadTimeoutError:
            logger.warning("There was a timeout error accessing the Kubernetes API. Retrying request.", exc_info=True)
            time.sleep(1)
        except Exception:
            logger.exception("Unknown error in NamespaceWatcher. Failing")
            raise
        else:
            logger.warning(
                "Watch died gracefully, starting back up with last_resource_version: %s", state["lastResourceVersion"]
            )


def process_namespaces(queue: Queue, state: Dict[str, Any], replicator_id: int) -> int:  # type: ignore
    logger.info("Started Namespace Processor Id: %s", replicator_id)
    namespace_event: Optional[Dict[str, Any]] = None

    while True:
        try:
            namespace_event = cast(Dict[str, Any], queue.get(block=True, timeout=None))

            if namespace_event["type"] == "ADDED":
                process_added_event(namespace=namespace_event["raw_object"])
            elif namespace_event["type"] == "DELETED":
                process_removed_event(namespace=namespace_event["raw_object"])
            else:
                logger.debug("Skipping Namespace event: %s", namespace_event)
        except Exception:
            logger.exception("Failed to process Namespace event: %s", namespace_event)
        finally:
            namespace_event = None
            time.sleep(1)
