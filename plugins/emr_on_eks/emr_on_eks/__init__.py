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
import time
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
def deploy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug("Running emr_on_eks deploy!")
    sh.run(f"echo 'Team name: {team_context.name} | Plugin ID: {plugin_id}'")
    cluster_name = f"orbit-{context.name}"
    virtual_cluster_name = f"orbit-{context.name}-{team_context.name}"
    delete_virtual_cluster(cluster_name, virtual_cluster_name)

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
    _logger.info("deploying emr on eks iam policy")
    cdk_deploy(
        stack_name=f"orbit-{context.name}-{team_context.name}-emr-on-eks",
        app_filename=os.path.join(ORBIT_EMR_ON_EKS_ROOT, "cdk.py"),
        context=context,
        team_context=team_context,
        parameters=parameters,
    )
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

    except Exception as e:
        if "A virtual cluster already exists in the given namespace" in str(e):
            pass
        else:
            raise


@hooks.destroy
def destroy(
    plugin_id: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    _logger.debug("Running emr_on_eks destroy!")
    sh.run(f"echo 'Team name: {team_context.name} | Plugin ID: {plugin_id}'")
    cluster_name = f"orbit-{context.name}"
    virtual_cluster_name = f"orbit-{context.name}-{team_context.name}"
    delete_virtual_cluster(cluster_name, virtual_cluster_name)

    cdk_destroy(
        stack_name=f"orbit-{context.name}-{team_context.name}-emr-on-eks",
        app_filename=os.path.join(ORBIT_EMR_ON_EKS_ROOT, "cdk.py"),
        context=context,
        team_context=team_context,
        parameters=parameters,
    )


def delete_virtual_cluster_jobs(virtual_cluster_id: str) -> None:
    emrc = boto3.client("emr-containers")
    if virtual_cluster_id:
        list_job_runs_response = emrc.list_job_runs(
            virtualClusterId=virtual_cluster_id,
            states=["PENDING", "SUBMITTED", "RUNNING", "CANCEL_PENDING"],
        )
        if "jobRuns" in list_job_runs_response:
            for jr in list_job_runs_response["jobRuns"]:
                job_id, job_name = (jr["id"], jr["name"])
                _logger.info(f"Deleting job {job_id}:{job_name}")
                try:
                    response = emrc.cancel_job_run(id=job_id, virtualClusterId=virtual_cluster_id)
                    if 200 == response["ResponseMetadata"]["HTTPStatusCode"]:
                        _logger.debug(f"Deleted job {job_id}:{job_name}")
                except Exception as e:
                    _logger.error(f"Failed to delete job {job_id}:{job_name}")
                    _logger.error("Error  %s", e)
        else:
            _logger.info(f"No job runs in virtual cluster {virtual_cluster_id}")


def delete_virtual_cluster(eks_cluster_name: str, virtual_cluster_name: str) -> None:
    emr = boto3.client("emr-containers")
    paginator = emr.get_paginator("list_virtual_clusters")
    response_iterator = paginator.paginate(
        containerProviderId=eks_cluster_name,
        containerProviderType="EKS",
        states=[
            "RUNNING",
        ],
        PaginationConfig={
            # can't expect to have so many virtual clusters and teams concurrently on the same env
            "MaxItems": 10000,
            "PageSize": 400,
        },
    )
    _logger.debug("finding emr virtual clusters...")
    for vcri in response_iterator:
        if "virtualClusters" in vcri:
            for vc in vcri["virtualClusters"]:
                _logger.debug("Emr virtual cluster found: %s", vc["name"])
                if vc["name"] == virtual_cluster_name:
                    try:
                        # Delete all running/submitted jobs before deleting virtual cluster
                        delete_virtual_cluster_jobs(vc["id"])
                        time.sleep(120)
                        delete_response = emr.delete_virtual_cluster(id=vc["id"])
                        _logger.debug("delete_virtual_cluster:", delete_response)
                    except Exception as e:
                        _logger.exception("error deleting virtual cluster")
                        _logger.error("Error  %s", e)
        else:
            _logger.info(f"No EMR Virtual cluster in EKS cluster {eks_cluster_name}")
    _logger.debug("end of emr virtual clusters deletion")
