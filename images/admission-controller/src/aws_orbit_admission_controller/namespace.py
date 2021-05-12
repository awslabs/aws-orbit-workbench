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
import json
import logging
import subprocess
import sys
from typing import Any, Dict

import jsonpatch
from aws_orbit_admission_controller import load_config, run_command
from flask import jsonify
from kubernetes.client import *


def should_install_team_package(logger: logging.Logger, request: Dict[str, Any]) -> bool:
    if "dryRun" in request and request["dryRun"]:
        logger.info("Dry run - Skip Install")
        return False

    spec = request["object"]["spec"]
    space = spec["space"]
    if space == "team":
        return False

    return True


def process_request(logger: logging.Logger, request: Dict[str, Any]) -> Any:
    logger.debug("loading kubeconfig")
    load_config()
    spec = request["object"]["spec"]
    name = request["object"]["metadata"]["name"]
    modified_spec = copy.deepcopy(spec)
    logger.info("processing namespace settings")
    logger.debug("request: %s", request)

    if not should_install_team_package(logger, request):
        return jsonify(
            {
                "response": {
                    "allowed": True,
                    "uid": request["uid"],
                }
            }
        )
    # env = spec["env"]
    team = spec["team"]
    user = spec["user"]
    user_email = spec["email"]
    namespace = name

    logger.debug("new namespace: %s,%s,%s,%s", team, user, user_email, namespace)

    team_context = get_team_context(logger, team)
    helm_repo_url = team_context["HelmRepository"]
    logger.debug("Adding Helm Repository: %s at %s", team, helm_repo_url)
    helm_release = f"{namespace}-orbit-team"
    # add the team repo
    run_command(logger, f"helm repo add {team} {helm_repo_url}")
    # install the helm package for this user space
    install_helm_chart(helm_release, logger, namespace, team, user, user_email)

    try:
        modified_spec["metadata"]["annotations"]["orbit/helm"] = f"{namespace}-orbit-team"
    except KeyError:
        pass

    logger.info("Helm release %s installed at %s", helm_release, namespace)
    patch = jsonpatch.JsonPatch.from_diff(spec, modified_spec)
    return jsonify(
        {
            "response": {
                "allowed": True,
                "uid": request["uid"],
                "patch": base64.b64encode(str(patch).encode()).decode(),
                "patchtype": "JSONPatch",
            }
        }
    )


def install_helm_chart(helm_release, logger, namespace, team, user, user_email):
    try:
        # cmd = "/usr/local/bin/helm repo list"
        cmd = (
            f"/usr/local/bin/helm upgrade --install --devel --debug --namespace {namespace} "
            f"{helm_release} {team}/orbit-user "
            f"--set user={user},user_email={user_email},namespace={namespace}"
        )

        logger.debug("running cmd: %s", cmd)
        subprocess.check_output(cmd.split(" "), stderr=sys.stderr)
    except subprocess.CalledProcessError as exc:
        logger.debug("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output.decode("utf-8")))
        raise Exception(exc.output.decode("utf-8"))


def get_team_context(logger, team):
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
