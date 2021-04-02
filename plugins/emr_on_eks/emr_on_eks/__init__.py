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

import logging
import os
from typing import TYPE_CHECKING, Any, Dict

import boto3
from aws_orbit import sh
from aws_orbit.plugins import hooks
from aws_orbit.plugins.helpers import cdk_deploy, cdk_destroy

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger("aws_orbit")

PLUGIN_ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
ORBIT_EMR_ON_EKS_ROOT = os.path.dirname(os.path.abspath(__file__))


@hooks.deploy
def deploy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Running emr_on_eks deploy!")
    sh.run(f"echo 'Team name: {team_context.name} | Plugin ID: {plugin_id}'")
    cluster_name = f"orbit-{context.name}"
    virtual_cluster_name = f"orbit-{context.name}-{team_context.name}"
    sh.run(
        f"eksctl create iamidentitymapping --cluster {cluster_name} "
        + f'--namespace {team_context.name} --service-name "emr-containers"'
    )
    if team_context.eks_pod_role_arn is None:
        raise ValueError("Pod Role arn required")
    role_name = team_context.eks_pod_role_arn.split("/")[1]
    sh.run(
        f" aws emr-containers update-role-trust-policy \
       --cluster-name {cluster_name} \
       --namespace {team_context.name} \
       --role-name {role_name}"
    )
    emr = boto3.client("emr-containers")

    try:
        _logger.info(f"creating emr virtual cluster {virtual_cluster_name}")
        response = emr.create_virtual_cluster(
            name=virtual_cluster_name,
            containerProvider={
                "id": cluster_name,
                "type": "EKS",
                "info": {"eksInfo": {"namespace": team_context.name}},
            },
            tags={"Env": context.name, "TeamSpace": team_context.name},
        )

        _logger.debug("create_virtual_cluster:", response)
        parameters["virtual_cluster_id"] = response["id"]
        parameters["virtual_name"] = response["name"]
        parameters["virtual_arn"] = response["arn"]
        cdk_deploy(
            stack_name=f"orbit-{context.name}-{team_context.name}-emr-on-eks",
            app_filename=os.path.join(ORBIT_EMR_ON_EKS_ROOT, "cdk.py"),
            context=context,
            team_context=team_context,
            parameters=parameters,
        )

    except Exception as e:
        if "A virtual cluster already exists in the given namespace" in str(e):
            pass
        else:
            raise


@hooks.destroy
def destroy(plugin_id: str, context: "Context", team_context: "TeamContext", parameters: Dict[str, Any]) -> None:
    _logger.debug("Running emr_on_eks destroy!")
    sh.run(f"echo 'Team name: {team_context.name} | Plugin ID: {plugin_id}'")

    virtual_cluster_name = f"orbit-{context.name}-{team_context.name}"
    emr = boto3.client("emr-containers")
    response = emr.list_virtual_clusters(
        containerProviderId=f"orbit-{context.name}", containerProviderType="EKS", maxResults=500
    )
    if "virtualClusters" in response:
        for c in response["virtualClusters"]:
            if c["name"] == virtual_cluster_name:
                try:
                    delete_response = emr.delete_virtual_cluster(id=c["id"])
                    _logger.debug("delete_virtual_cluster:", delete_response)
                except Exception as e:
                    _logger.warning(e)
                    pass

    cdk_destroy(
        stack_name=f"orbit-{context.name}-{team_context.name}-emr-on-eks",
        app_filename=os.path.join(ORBIT_EMR_ON_EKS_ROOT, "cdk.py"),
        context=context,
        team_context=team_context,
        parameters=parameters,
    )
