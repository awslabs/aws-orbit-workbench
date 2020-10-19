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
from typing import Any, Dict

import yaml

from datamaker_cli import sh
from datamaker_cli.manifest import Manifest, SubnetKind, TeamManifest
from datamaker_cli.services import cfn

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST: Dict[str, Any] = {
    "apiVersion": "eksctl.io/v1alpha5",
    "kind": "ClusterConfig",
    "metadata": {"name": None, "region": None},
    "vpc": {"id": None, "cidr": None, "subnets": {"private": None, "public": None}},
    "iam": {"serviceRoleARN": None},
}


def create_nodegroup_structure(team: TeamManifest, env_name: str) -> Dict[str, Any]:
    return {
        "name": team.name,
        "privateNetworking": True,
        "instanceType": team.instance_type,
        "minSize": team.nodes_num_min,
        "desiredCapacity": team.nodes_num_desired,
        "maxSize": team.nodes_num_max,
        "volumeSize": team.local_storage_size,
        "ssh": {"allow": False},
        "labels": {"team": team.name},
        "tags": {"Env": f"datamaker-{env_name}"},
        "iam": {"instanceRoleARN": team.eks_nodegroup_role_arn},
    }


def generate_manifest(manifest: Manifest, filename: str, name: str) -> str:

    # Fill cluster wide configs
    MANIFEST["metadata"]["name"] = name
    MANIFEST["metadata"]["region"] = manifest.region
    MANIFEST["vpc"]["id"] = manifest.vpc.vpc_id
    MANIFEST["vpc"]["cidr"] = manifest.vpc.cidr_block
    for kind in (SubnetKind.private, SubnetKind.public):
        MANIFEST["vpc"]["subnets"][kind.value] = {
            s.availability_zone: {"id": s.subnet_id, "cidr": s.cidr_block}
            for s in manifest.vpc.subnets
            if s.kind is kind
        }
    MANIFEST["iam"]["serviceRoleARN"] = manifest.eks_cluster_role_arn

    # Fill nodegroups configs
    if manifest.teams:
        MANIFEST["managedNodeGroups"] = []
        for team in manifest.teams:
            MANIFEST["managedNodeGroups"].append(create_nodegroup_structure(team=team, env_name=manifest.name))

    # Env
    MANIFEST["managedNodeGroups"].append(
        {
            "name": "env",
            "privateNetworking": True,
            "instanceType": "t3.medium",
            "minSize": 2,
            "desiredCapacity": 2,
            "maxSize": 2,
            "volumeSize": 64,
            "ssh": {"allow": False},
            "labels": {"team": "env"},
            "tags": {"Env": "datamaker"},
            "iam": {"instanceRoleARN": manifest.eks_env_nodegroup_role_arn},
        }
    )

    output_filename = f"{manifest.filename_dir}/.datamaker.out/{manifest.name}/eksctl/cluster.yaml"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, "w") as file:
        yaml.dump(MANIFEST, file, sort_keys=False)

    _logger.debug("output_filename: %s", output_filename)
    return output_filename


def deploy(manifest: Manifest, filename: str) -> None:
    manifest.read_ssm()
    stack_name: str = f"datamaker-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    if cfn.does_stack_exist(stack_name=final_eks_stack_name) is False:
        _logger.debug("Synthetizing the EKSCTL manifest")
        output_filename = generate_manifest(manifest=manifest, filename=filename, name=stack_name)
        _logger.debug("Deploying EKSCTL resources")
        sh.run(f"eksctl create cluster -f {output_filename} --write-kubeconfig")
    else:
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
    _logger.debug("EKSCTL deployed")


def destroy(manifest: Manifest, filename: str) -> None:
    stack_name: str = f"datamaker-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    if cfn.does_stack_exist(stack_name=final_eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
        manifest.read_ssm()
        output_filename = generate_manifest(manifest=manifest, filename=filename, name=stack_name)
        sh.run(f"eksctl delete cluster -f {output_filename}")
        _logger.debug("EKSCTL destroyed")
