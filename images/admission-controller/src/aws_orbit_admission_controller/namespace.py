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
from typing import Any, Dict

import jsonpatch
# from aws_orbit_admission_controller import load_config
from flask import jsonify
from kubernetes.client import *

from aws_orbit_admission_controller import load_config, run_command, install_chart

def should_install_team_package(logger: logging.Logger, request: Dict[str, Any]) -> bool:
    spec = request["object"]

    if "dryRun" in request and request["dryRun"] == True:
        logger.info("Dry run - Skip Install")
        return False

    if "metadata" not in spec or "labels" not in spec["metadata"]:
        logger.info("Missing labels - Skip Install")
        return False

    if "orbit/user-space" not in spec["metadata"]["labels"]:
        logger.info("Missing orbit/user-space - Skip Install")
        return False

    return True


def process_request(logger: logging.Logger, request: Dict[str, Any]) -> Any:
    logger.info("loading kubeconfig")
    load_config()
    spec = request["object"]
    modified_spec = copy.deepcopy(spec)
    logger.info("processing namesace:")
    logger.info("request: %s", request)

    if not should_install_team_package(logger, request):
        return jsonify(
            {
                "response": {
                    "allowed": True,
                    "uid": request["uid"],
                }
            }
        )
    # env = spec["metadata"]["labels"]["orbit/env"]
    team = spec["metadata"]["labels"]["orbit/team"]
    user = spec["metadata"]["labels"]["orbit/user"]
    user_email = spec["metadata"]["annotations"]["owner"]
    namespace = spec["metadata"]["name"]
    logger.info("new namespace: %s,%s,%s,%s", team, user, user_email, namespace)
    try:
        api_instance = CoreV1Api()
        team_context_cf: V1ConfigMap = api_instance.read_namespaced_config_map("orbit-team-context", team)
        team_context_str = team_context_cf.data["team"]

        logger.info("team context: %s", team_context_str)
        team_context: Dict[str, Any] = json.loads(team_context_str)
        logger.info("team context keys: %s", team_context.keys())
    except Exception as e:
        logger.error("Error during fetching team context configmap")
        raise e
    helm_repo_url = team_context["HelmRepository"]
    logger.debug("Adding Helm Repository: %s at %s", team, helm_repo_url)

    run_command(logger, f"helm repo add {team} {helm_repo_url}")
    install_chart(logger, team, namespace, f'{namespace}-orbit-team', "orbit-user")

    try:
        modified_spec["metadata"]["annotations"]["orbit/helm"] = f'{namespace}-orbit-team'
    except KeyError:
        pass

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
