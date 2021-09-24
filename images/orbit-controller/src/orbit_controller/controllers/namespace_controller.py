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
import random
import string
import time
from typing import Any, Dict, Optional

import kopf
from kubernetes.client import CoreV1Api, V1ConfigMap
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dynamic_client, load_config, run_command
from orbit_controller.utils import poddefault_utils, userspace_utils


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, logger: kopf.Logger, **_: Any) -> None:
    settings.persistence.progress_storage = kopf.MultiProgressStorage(
        [
            kopf.AnnotationsProgressStorage(prefix="orbit.aws"),
            kopf.StatusProgressStorage(field="status.orbit-aws"),
        ]
    )
    settings.persistence.finalizer = "namespace-controller.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))


def _should_index_podsetting(labels: kopf.Labels, **_: Any) -> bool:
    return labels.get("orbit/space") == "team" and "orbit/team" in labels and "orbit/disable-watcher" not in labels


@kopf.index(ORBIT_API_GROUP, ORBIT_API_VERSION, "podsettings", when=_should_index_podsetting)  # type: ignore
def podsettings_idx(
    namespace: str, name: str, labels: kopf.Labels, spec: kopf.Spec, **_: Any
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Index of podsettings by team"""
    return {
        labels["orbit/team"]: {
            "namespace": namespace,
            "name": name,
            "labels": labels,
            "spec": spec,
        }
    }


def _install_helm_chart(
    helm_release: str,
    namespace: str,
    team: str,
    user: str,
    user_email: str,
    user_efsapid: str,
    repo: str,
    package: str,
    logger: kopf.Logger,
) -> None:
    # try to uninstall first
    try:
        cmd = f"helm uninstall --debug {helm_release} -n {team}"
        logger.debug("running cmd: %s", cmd)
        output = run_command(cmd)
        logger.debug(output)
        logger.info("finished cmd: %s", cmd)
    except Exception:
        logger.debug("helm uninstall did not find the release")

    cmd = (
        f"/usr/local/bin/helm upgrade --install --devel --debug --namespace {team} "
        f"{helm_release} {repo}/{package} "
        f"--set user={user},user_email={user_email},namespace={namespace},user_efsapid={user_efsapid}"
    )

    logger.debug("running cmd: %s", cmd)
    output = run_command(cmd)
    logger.debug(output)
    logger.info("finished cmd: %s", cmd)


def _uninstall_chart(helm_release: str, namespace: str, logger: kopf.Logger) -> None:
    cmd = f"/usr/local/bin/helm uninstall --debug --namespace {namespace} {helm_release}"
    logger.debug("running uninstall cmd: %s", cmd)
    output = run_command(cmd)
    logger.debug(output)
    logger.info("finished uninstall cmd: %s", cmd)


def _get_team_context(team: str, logger: kopf.Logger) -> Dict[str, Any]:
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


def _should_process_namespace(annotations: kopf.Annotations, labels: kopf.Labels, **_: Any) -> bool:
    return "orbit/helm-chart-installation" not in annotations and labels.get("orbit/space", None) == "user"


@kopf.on.resume("namespaces", when=_should_process_namespace)  # type: ignore
@kopf.on.create("namespaces", when=_should_process_namespace)
def install_team_charts(
    name: str,
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    patch: kopf.Patch,
    podsettings_idx: kopf.Index[str, Dict[str, Any]],
    logger: kopf.Logger,
    **_: Any,
) -> str:
    logger.debug("loading kubeconfig")
    load_config()

    logger.info("processing namespace")
    logger.debug("namespace: %s", name)

    env = labels.get("orbit/env", None)
    space = labels.get("orbit/space", None)
    team = labels.get("orbit/team", None)
    user = labels.get("orbit/user", None)
    user_efsapid = labels.get("orbit/efs-access-point-id", None)
    user_email = annotations.get("owner", None)

    logger.debug("new namespace: %s,%s,%s,%s", team, user, user_email, name)

    if not env or not space or not team or not user or not user_efsapid or not user_email:
        logger.error(
            (
                "All of env, space, team, user, user_efsapid, and user_email are required."
                "Found: %s, %s, %s, %s, %s, %s"
            ),
            env,
            space,
            team,
            user,
            user_efsapid,
            user_email,
        )
        patch["metadata"] = {"annotations": {"orbit/helm-chart-installation": "Skipped"}}
        return "Skipping"

    client = dynamic_client()
    userspace = userspace_utils.construct(
        name=name,
        env=env,
        space=space,
        team=team,
        user=user,
        user_efsapid=user_efsapid,
        user_email=user_email,
    )
    try:
        userspace_utils.create_userspace(namespace=name, userspace=userspace, client=client, logger=logger)
    except Exception as e:
        logger.warn("Failed to create UserSpace %s: %s", name, str(e))

    team_context = _get_team_context(team=team, logger=logger)
    logger.info("team context keys: %s", team_context.keys())
    helm_repo_url = team_context["UserHelmRepository"]
    logger.debug("Adding Helm Repository: %s at %s", team, helm_repo_url)
    repo = f"{team}--userspace"
    # add the team repo
    unique_hash = "".join(random.choice(string.ascii_lowercase) for i in range(6))
    run_command(f"helm repo add {repo} {helm_repo_url}")
    try:
        # In isolated envs, we cannot refresh stable, and since we don't use it, we remove it
        run_command("helm repo remove stable")
    except Exception:
        logger.info("Tried to remove stable repo...got an error, but moving on")
    run_command("helm repo update")
    run_command(f"helm search repo --devel {repo} -o json > /tmp/{unique_hash}-charts.json")
    with open(f"/tmp/{unique_hash}-charts.json", "r") as f:
        charts = json.load(f)

    run_command(f"helm list -n {team} -o json > /tmp/{unique_hash}-releases.json")
    with open(f"/tmp/{unique_hash}-releases.json", "r") as f:
        releaseList = json.load(f)
        releases = [r["name"] for r in releaseList]
        logger.info("current installed releases: %s", releases)

    for chart in charts:
        chart_name = chart["name"].split("/")[1]
        helm_release = f"{name}-{chart_name}"
        # do not install again the chart if its already installed as some charts are not upgradable.
        # namespaces might
        if helm_release not in releaseList:
            # install the helm package for this user space
            _install_helm_chart(
                helm_release=helm_release,
                namespace=name,
                team=team,
                user=user,
                user_email=user_email,
                user_efsapid=user_efsapid,
                repo=repo,
                package=chart_name,
                logger=logger,
            )
            logger.info("Helm release %s installed at %s", helm_release, name)

    logger.info("Copying PodDefaults from Team")
    # Construct pseudo poddefaults for each podsetting in the team namespace
    poddefaults = [
        poddefault_utils.construct(
            name=ps["name"],
            desc=ps["spec"].get("desc", ""),
            labels={"orbit/space": "team", "orbit/team": team},
        )
        for ps in podsettings_idx.get(team, [])
    ]
    poddefault_utils.copy_poddefaults_to_user_namespaces(
        client=client, poddefaults=poddefaults, user_namespaces=[name], logger=logger
    )

    patch["metadata"] = {"annotations": {"orbit/helm-chart-installation": "Complete"}}
    return "Complete"


@kopf.on.delete("namespaces", labels={"orbit/space": kopf.PRESENT})  # type: ignore
def uninstall_team_charts(
    name: str,
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    logger: kopf.Logger,
    **_: Any,
) -> str:
    logger.debug("loading kubeconfig")
    load_config()

    logger.info("processing removed namespace %s", name)
    space = labels.get("orbit/space", None)

    if space == "team":
        logger.info("delete all namespaces that belong to the team %s", name)
        run_command(f"kubectl delete profile -l orbit/team={name}")
        time.sleep(60)
        run_command(f"kubectl delete namespace -l orbit/team={name},orbit/space=user")
        logger.info("all namespaces that belong to the team %s are deleted", name)
    elif space == "user":
        env = labels.get("orbit/env", None)
        team = labels.get("orbit/team", None)
        user = labels.get("orbit/user", None)
        user_email = annotations.get("owner", None)

        logger.debug("removed namespace: %s,%s,%s,%s", team, user, user_email, name)

        if not env or not space or not team or not user or not user_email:
            logger.error(
                "All of env, space, team, user, and user_email are required. Found: %s, %s, %s, %s, %s",
                env,
                space,
                team,
                user,
                user_email,
            )
            return "Skipping"

        team_context = _get_team_context(team=team, logger=logger)
        logger.info("team context keys: %s", team_context.keys())
        helm_repo_url = team_context["UserHelmRepository"]
        repo = f"{team}--userspace"
        # add the team repo
        unique_hash = "".join(random.choice(string.ascii_lowercase) for i in range(6))
        run_command(f"helm repo add {repo} {helm_repo_url}")
        run_command(f"helm search repo --devel {repo} -o json > /tmp/{unique_hash}-charts.json")
        with open(f"/tmp/{unique_hash}-charts.json", "r") as f:
            charts = json.load(f)
        run_command(f"helm list -n {team} -o json > /tmp/{unique_hash}-releases.json")
        with open(f"/tmp/{unique_hash}-releases.json", "r") as f:
            releaseList = json.load(f)
            releases = [r["name"] for r in releaseList]
            logger.info("current installed releases: %s", releases)

        for chart in charts:
            chart_name = chart["name"].split("/")[1]
            helm_release = f"{name}-{chart_name}"
            if helm_release in releases:
                _uninstall_chart(helm_release=helm_release, namespace=team, logger=logger)

    return "Complete"
