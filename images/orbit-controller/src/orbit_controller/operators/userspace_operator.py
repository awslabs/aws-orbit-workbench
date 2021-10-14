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
    settings.persistence.finalizer = "userspace-operator.orbit.aws/kopf-finalizer"
    settings.posting.level = logging.getLevelName(os.environ.get("EVENT_LOG_LEVEL", "INFO"))


def _should_index_podsetting( spec: kopf.Spec, **_: Any) -> bool:
    return spec.get("space") == "team" and "team" in spec #and "orbit/disable-watcher" not in labels


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
) -> bool:
    install_status= True
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
    try:
        logger.debug("running cmd: %s", cmd)
        output = run_command(cmd)
        logger.debug(output)
        logger.info("finished cmd: %s", cmd)
    except Exception:
        logger.error("errored cmd: %s", cmd)
        install_status= False
    return install_status


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


def _should_process_userspace(annotations: kopf.Annotations, spec: kopf.Spec, **_: Any) -> bool:
    return "orbit/helm-chart-installation" not in annotations and spec.get("space", None) == "user"


@kopf.on.resume(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "userspaces",
    # field="status.installation.installationStatus",
    # value=kopf.ABSENT,
    when=_should_process_userspace
)
@kopf.on.create(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "userspaces",
    # field="status.installation.installationStatus",
    # value=kopf.ABSENT,
    when=_should_process_userspace
)
def install_team(
        name: str,
        meta: kopf.Meta,
        spec: kopf.Spec,
        status: kopf.Status,
        patch: kopf.Patch,
        logger: kopf.Logger,
        **_: Any
) -> str:
    logger.debug("loading kubeconfig")
    load_config()

    logger.info("processing userspace cr")
    logger.debug("namespace: %s", name)

    env = spec.get("env", None)
    space = spec.get("space", None)
    team = spec.get("team", None)
    user = spec.get("user", None)
    user_efsapid = spec.get("userEfsApId", None)
    user_email = spec.get("userEmail", None)

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
    # userspace = userspace_utils.construct(
    #     name=name,
    #     env=env,
    #     space=space,
    #     team=team,
    #     user=user,
    #     user_efsapid=user_efsapid,
    #     user_email=user_email,
    # )
    # try:
    #     userspace_utils.create_userspace(namespace=name, userspace=userspace, client=client, logger=logger)
    # except Exception as e:
    #     logger.warn("Failed to create UserSpace %s: %s", name, str(e))

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
            install_status= _install_helm_chart(
                helm_release=helm_release,
                namespace=name,
                team=team,
                user=user,
                user_email=user_email,
                user_efsapid=user_efsapid,
                repo=repo,
                package=chart_name,
                logger=logger
            )
            if install_status:
                logger.info("Helm release %s installed at %s", helm_release, name)
                continue
            else:
                patch["status"] = {"installation": {"installationStatus": "Failed", "chart_name": chart_name }}
                return 'Failed'


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
    patch["status"] = {"installation": {"installationStatus": "Installed"}}

    return "Installed"


@kopf.on.delete(ORBIT_API_GROUP, ORBIT_API_VERSION, "userspaces")
def uninstall_team(**_: Any) -> str:
    return "Uninstalled"


# -------------------------
#
# apiVersion: orbit.aws/v1
# kind: UserSpace
# metadata:
#   name: "lake-admin-ssriche"
# spec:
#     env: "dev-env"
#     space: "user"
#     team: "lake-admin"
#     user: "ssriche"
#     userEfsApId: "fsap-0eb4feaefabd77d78"
#     userEmail: "ssriche@amazon.com"