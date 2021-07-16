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
import subprocess
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from aws_orbit import utils
from aws_orbit.plugins import hooks
from aws_orbit.remote_files import helm, kubectl
from aws_orbit.services import ec2
from aws_orbit.services.ec2 import IpPermission, UserIdGroupPair

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext
_logger: logging.Logger = logging.getLogger("aws_orbit")
TEAM_CHARTS_PATH = os.path.join(os.path.dirname(__file__), "charts", "team")
USER_CHARTS_PATH = os.path.join(os.path.dirname(__file__), "charts", "user")


def run_command(cmd: str) -> str:
    """ Module to run shell commands. """
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, timeout=29, universal_newlines=True)
    except subprocess.CalledProcessError as exc:
        _logger.debug("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output))
        raise Exception(exc.output)
    return output


@hooks.deploy
def deploy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug("Team Env name: %s | Team name: %s", context.name, team_context.name)
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug("plugin_id: %s", plugin_id)
    release_name = f"{team_context.name}-{plugin_id}"
    _logger.info("Checking Chart %s is installed...", release_name)

    fs_name = f"lustre-{team_context.name}-fs-{plugin_id}"

    vars: Dict[str, Optional[str]] = dict(
        team=team_context.name,
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        plugin_id=plugin_id,
        deploymentType="SCRATCH_2",
        sg=team_context.team_security_group_id,
        subnet=context.networking.data.nodes_subnets[0],
        s3importpath=f"s3://{team_context.scratch_bucket}/{team_context.name}/lustre",
        s3exportpath=f"s3://{team_context.scratch_bucket}/{team_context.name}/lustre",
        storage=parameters["storage"] if "storage" in parameters else "1200Gi",
        folder=parameters["folder"] if "folder" in parameters else "data",
        k8s_utilities_image=f"{context.images.k8s_utilities.repository}:{context.images.k8s_utilities.version}",
        fs_name=fs_name,
    )

    if not helm.is_exists_chart_release(release_name, team_context.name):
        _logger.info("Chart %s already installed, skipping installation", release_name)

        ec2.authorize_security_group_ingress(
            group_id=cast(str, team_context.team_security_group_id),
            ip_permissions=[
                IpPermission(
                    from_port=988,
                    to_port=988,
                    ip_protocol="tcp",
                    user_id_group_pairs=[
                        UserIdGroupPair(
                            description="All from Cluster",
                            group_id=cast(str, context.cluster_sg_id),
                        )
                    ],
                )
            ],
        )

        chart_path = helm.create_team_charts_copy(
            team_context=team_context, path=TEAM_CHARTS_PATH, target_path=plugin_id
        )
        _logger.debug("package dir")
        utils.print_dir(TEAM_CHARTS_PATH)
        _logger.debug("copy chart dir")
        utils.print_dir(chart_path)

        if not team_context.team_helm_repository:
            raise Exception("Missing team helm repository")

        repo_location = team_context.team_helm_repository

        repo = team_context.name
        helm.add_repo(repo=repo, repo_location=repo_location)
        chart_name, chart_version, chart_package = helm.package_chart(
            repo=repo, chart_path=os.path.join(chart_path, "fsx-storageclass"), values=vars
        )
        helm.install_chart_no_upgrade(
            repo=repo,
            namespace=team_context.name,
            name=release_name,
            chart_name=chart_name,
            chart_version=chart_version,
        )

    get_user_pv(fs_name, plugin_id, context, team_context, vars)

    # install this package at the user helm repository such that its installed on every user space
    chart_path = helm.create_team_charts_copy(team_context=team_context, path=USER_CHARTS_PATH, target_path=plugin_id)

    if not team_context.user_helm_repository:
        raise Exception("Missing user helm repository")
    user_location = team_context.user_helm_repository

    user_repo = team_context.name + "--user"
    helm.add_repo(repo=user_repo, repo_location=user_location)

    chart_name, chart_version, chart_package = helm.package_chart(
        repo=user_repo, chart_path=os.path.join(chart_path, "fsx-filesystem"), values=vars
    )
    _logger.info(f"Lustre Helm Chart {chart_name}@{chart_version} installed for {team_context.name} at {chart_package}")


def get_user_pv(
    fs_name: str, plugin_id: str, context: "Context", team_context: "TeamContext", vars: Dict[str, Optional[str]]
) -> None:
    for i in range(0, 15):
        run_command(f"kubectl get pvc -n {team_context.name} {fs_name} -o json > /tmp/pvc.json")
        with open("/tmp/pvc.json", "r") as f:
            pvc = json.load(f)
        if "spec" in pvc and "volumeName" in pvc["spec"] and pvc["spec"]["volumeName"]:
            volumeName = pvc["spec"]["volumeName"]
            run_command(f"kubectl get pv {volumeName} -o json > /tmp/pv.json")
            with open("/tmp/pv.json", "r") as f:
                team_pv = json.load(f)
                _logger.debug("team pv: %s", json.dumps(team_pv, sort_keys=True, indent=4))
            if "spec" in team_pv:
                vars["dnsname"] = team_pv["spec"]["csi"]["volumeAttributes"]["dnsname"]
                vars["mountname"] = team_pv["spec"]["csi"]["volumeAttributes"]["mountname"]
                vars["csiProvisionerIdentity"] = team_pv["spec"]["csi"]["volumeAttributes"][
                    "storage.kubernetes.io/csiProvisionerIdentity"
                ]
                vars["volumeHandle"] = team_pv["spec"]["csi"]["volumeHandle"]
                _logger.info(f"FSX Volume is {volumeName}")
                break

        _logger.info("FSX Volume not ready. Waiting a min")
        time.sleep(60)
        kubectl.write_kubeconfig(context=context)
    else:
        raise Exception(f"FSX Volume is not ready for plugin {plugin_id}")


@hooks.destroy
def destroy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    plugin_id = plugin_id.replace("_", "-")
    _logger.debug(
        "Delete Plugin %s of Team Env name: %s | Team name: %s",
        plugin_id,
        context.name,
        team_context.name,
    )
    release_name = f"{team_context.name}-{plugin_id}"
    try:
        helm.uninstall_chart(release_name, namespace=team_context.name)
    except Exception as e:
        _logger.error(str(e))
