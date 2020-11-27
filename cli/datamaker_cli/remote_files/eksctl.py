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
import pprint
from typing import Any, Dict

import yaml

from datamaker_cli import sh
from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.subnet import SubnetKind
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.services import cfn

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST: Dict[str, Any] = {
    "apiVersion": "eksctl.io/v1alpha5",
    "kind": "ClusterConfig",
    "metadata": {"name": None, "region": None},
    "vpc": {"id": None, "cidr": None, "subnets": {"private": None, "public": None}},
    "iam": {"serviceRoleARN": None},
    "cloudWatch": {"clusterLogging": {"enableTypes": ["*"]}},
}


def create_nodegroup_structure(team: TeamManifest, env_name: str) -> Dict[str, Any]:
    if team.eks_nodegroup_role_arn is None:
        _logger.debug(f"ValueError: team.eks_nodegroup_role_arn: {team.eks_nodegroup_role_arn}")
        return {"name": team.name}
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


def generate_manifest(manifest: Manifest, name: str, output_teams: bool = True) -> str:

    # Fill cluster wide configs
    MANIFEST["metadata"]["name"] = name
    MANIFEST["metadata"]["region"] = manifest.region
    MANIFEST["vpc"]["clusterEndpoints"] = {"publicAccess": True, "privateAccess": manifest.isolated_networking}
    MANIFEST["vpc"]["id"] = manifest.vpc.vpc_id
    MANIFEST["vpc"]["cidr"] = manifest.vpc.cidr_block
    private_kind: SubnetKind = SubnetKind.isolated if manifest.isolated_networking else SubnetKind.private
    for kind in (private_kind, SubnetKind.public):
        eksctl_kind: str = "private" if kind is private_kind else kind.value
        MANIFEST["vpc"]["subnets"][eksctl_kind] = {
            s.availability_zone: {"id": s.subnet_id, "cidr": s.cidr_block}
            for s in manifest.vpc.subnets
            if s.kind is kind
        }
    MANIFEST["iam"]["serviceRoleARN"] = manifest.eks_cluster_role_arn
    MANIFEST["managedNodeGroups"] = []

    # Fill nodegroups configs
    if manifest.teams and output_teams:
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

    _logger.debug("eksctl manifest:\n%s", pprint.pformat(MANIFEST))
    output_filename = f"{manifest.filename_dir}/.datamaker.out/{manifest.name}/eksctl/cluster.yaml"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, "w") as file:
        yaml.dump(MANIFEST, file, sort_keys=False)

    _logger.debug("output_filename: %s", output_filename)
    return output_filename


def deploy_env(manifest: Manifest) -> None:
    stack_name: str = f"datamaker-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    _logger.debug("Synthetizing the EKSCTL Environment manifest")
    output_filename = generate_manifest(manifest=manifest, name=stack_name, output_teams=False)
    if not cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name):
        _logger.debug("Deploying EKSCTL Environment resources")
        sh.run(f"eksctl create cluster -f {output_filename} --write-kubeconfig --verbose 4")
    else:
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
    _logger.debug("EKSCTL deployed")


def deploy_teams(manifest: Manifest) -> None:
    stack_name: str = f"datamaker-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    _logger.debug("Synthetizing the EKSCTL Teams manifest")
    output_filename = generate_manifest(manifest=manifest, name=stack_name, output_teams=True)
    if cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name) and manifest.teams:
        teams = ",".join([t.name for t in manifest.teams])
        _logger.debug("Deploying EKSCTL Teams resources")
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
        sh.run(f"eksctl create nodegroup -f {output_filename} --include={teams} --verbose 4")
    _logger.debug("EKSCTL deployed")


def destroy_env(manifest: Manifest) -> None:
    stack_name: str = f"datamaker-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
        output_filename = generate_manifest(manifest=manifest, name=stack_name)
        sh.run(f"eksctl delete cluster -f {output_filename} --wait --verbose 4")
        _logger.debug("EKSCTL Envrionment destroyed")


def destroy_teams(manifest: Manifest) -> None:
    stack_name: str = f"datamaker-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name) and manifest.teams:
        teams = ",".join([t.name for t in manifest.teams])
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
        output_filename = generate_manifest(manifest=manifest, name=stack_name)
        sh.run(f"eksctl delete nodegroup -f {output_filename} --include={teams} --approve --wait --verbose 4")
        _logger.debug("EKSCTL Teams destroyed")
