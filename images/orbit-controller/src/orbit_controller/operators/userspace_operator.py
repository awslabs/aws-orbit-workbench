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
from typing import Any, Dict, Optional, cast

import boto3
import kopf
from kubernetes.client import CoreV1Api, V1ConfigMap
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dynamic_client, load_config, run_command
from orbit_controller.utils import poddefault_utils


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
) -> bool:
    install_status = True
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
        logger.warning("errored cmd: %s", cmd)
        install_status = False
    return install_status


def _create_user_efs_endpoint(user: str, team_name: str, team_efsid: str, env: str) -> Dict[str, Any]:
    efs = boto3.client("efs")

    return cast(
        Dict[str, str],
        efs.create_access_point(
            FileSystemId=team_efsid,
            PosixUser={"Uid": 1000, "Gid": 100},
            RootDirectory={
                "Path": f"/{team_name}/private/{user}",
                "CreationInfo": {"OwnerUid": 1000, "OwnerGid": 100, "Permissions": "770"},
            },
            Tags=[{"Key": "TeamSpace", "Value": team_name}, {"Key": "Env", "Value": env}],
        ),
    )


def _delete_user_efs_endpoint(user_name: str, user_namespace: str, logger: kopf.Logger, meta: kopf.Meta) -> None:
    efs = boto3.client("efs")

    logger.info(f"Fetching the EFS access point in the namespace {user_namespace} for user {user_name}")

    efs_access_point_id = meta.get("labels", {}).get("userEfsApId", None)

    logger.info(f"Deleting the EFS access point {efs_access_point_id} for user {user_name}")

    try:
        efs.delete_access_point(AccessPointId=efs_access_point_id)
        logger.info(f"Access point {efs_access_point_id} deleted")
    except efs.exceptions.AccessPointNotFound:
        logger.warning(f"Access point not found: {efs_access_point_id}")
    except efs.exceptions.InternalServerError as e:
        logger.warning(e)


def _uninstall_chart(helm_release: str, namespace: str, logger: kopf.Logger) -> bool:
    install_status = True
    cmd = f"/usr/local/bin/helm uninstall --debug --namespace {namespace} {helm_release}"
    try:
        logger.debug("running uninstall cmd: %s", cmd)
        output = run_command(cmd)
        logger.debug(output)
        logger.info("finished uninstall cmd: %s", cmd)
    except Exception:
        logger.error("errored cmd: %s", cmd)
        install_status = False
    return install_status


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


@kopf.on.resume(  # type: ignore
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "userspaces",
    field="status.userSpaceOperator.installationStatus",
    value=kopf.ABSENT,
    when=_should_process_userspace,
)
@kopf.on.create(
    ORBIT_API_GROUP,
    ORBIT_API_VERSION,
    "userspaces",
    field="status.userSpaceOperator.installationStatus",
    value=kopf.ABSENT,
    when=_should_process_userspace,
)
def install_team(
    name: str,
    meta: kopf.Meta,
    spec: kopf.Spec,
    status: kopf.Status,
    patch: kopf.Patch,
    podsettings_idx: kopf.Index[str, Dict[str, Any]],
    logger: kopf.Logger,
    **_: Any,
) -> str:
    logger.debug("loading kubeconfig")
    load_config()

    logger.info("processing userspace cr")
    logger.debug("namespace: %s", name)

    env = spec.get("env", None)
    space = spec.get("space", None)
    team = spec.get("team", None)
    user = spec.get("user", None)
    team_efsid = spec.get("teamEfsId", None)
    user_email = spec.get("userEmail", None)

    logger.debug("new namespace: %s,%s,%s,%s", team, user, user_email, name)

    if not env or not space or not team or not user or not team_efsid or not user_email:
        logger.error(
            ("All of env, space, team, user, team_efsid, and user_email are required." "Found: %s, %s, %s, %s, %s, %s"),
            env,
            space,
            team,
            user,
            team_efsid,
            user_email,
        )
        patch["metadata"] = {"annotations": {"orbit/helm-chart-installation": "Skipped"}}
        return "Skipping"

    client = dynamic_client()

    try:
        logger.info(f"Creating EFS endpoint for {team}-{user}...")
        efs_ep_resp = _create_user_efs_endpoint(user=user, team_name=team, team_efsid=team_efsid, env=env)
        access_point_id = efs_ep_resp.get("AccessPointId", "")
        logger.info(f"AccessPointId is {access_point_id}")
    except Exception as e:
        logger.error(f"Error while creating EFS access point for user_name={user} and team={team}: {e}")
        patch["status"] = {
            "userSpaceOperator": {"installationStatus": "Failed to create EFS AccessPoint", "exception": str(e)}
        }
        return "Failed"

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
            logger.info(f"install the helm package chart_name={chart_name} helm_release={helm_release}")
            install_status = _install_helm_chart(
                helm_release=helm_release,
                namespace=name,
                team=team,
                user=user,
                user_email=user_email,
                user_efsapid=access_point_id,
                repo=repo,
                package=chart_name,
                logger=logger,
            )
            if install_status:
                logger.info("Helm release %s installed at %s", helm_release, name)
                continue
            else:
                patch["status"] = {
                    "userSpaceOperator": {"installationStatus": "Failed to install", "chart_name": chart_name}
                }
                return "Failed"

    logger.info("Copying PodDefaults from Team")
    logger.info("podsettings_idx:%s", podsettings_idx)

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
    patch["metadata"] = {"labels": {"userEfsApId": access_point_id}}
    patch["status"] = {"userSpaceOperator": {"installationStatus": "Installed"}}

    return "Installed"


@kopf.on.delete(ORBIT_API_GROUP, ORBIT_API_VERSION, "userspaces")  # type: ignore
def uninstall_team_charts(
    name: str,
    annotations: kopf.Annotations,
    labels: kopf.Labels,
    spec: kopf.Spec,
    patch: kopf.Patch,
    logger: kopf.Logger,
    meta: kopf.Meta,
    **_: Any,
) -> str:
    logger.debug("loading kubeconfig")
    load_config()

    logger.info("processing removed namespace %s", name)
    space = spec.get("space", None)

    if space == "team":
        logger.info("delete all namespaces that belong to the team %s", name)
        run_command(f"kubectl delete profile -l orbit/team={name}")
        time.sleep(60)
        run_command(f"kubectl delete namespace -l orbit/team={name},orbit/space=user")
        logger.info("all namespaces that belong to the team %s are deleted", name)
    elif space == "user":
        env = spec.get("env", None)
        team = spec.get("team", None)
        user = spec.get("user", None)
        user_email = spec.get("userEmail", None)

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

        _delete_user_efs_endpoint(user_name=user, user_namespace=f"{team}-{user}", logger=logger, meta=meta)
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
                install_status = _uninstall_chart(helm_release=helm_release, namespace=team, logger=logger)

                if install_status:
                    logger.info("Helm release %s installed at %s", helm_release, name)
                    continue
                else:
                    patch["status"] = {
                        "userSpaceOperator": {"installationStatus": "Failed to uninstall", "chart_name": chart_name}
                    }
                    return "Failed"

    patch["status"] = {"userSpaceOperator": {"installationStatus": "Uninstalled"}}
    return "Uninstalled"
