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
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

import yaml
from aws_orbit import sh
from aws_orbit.changeset import ListChangeset
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.subnet import SubnetKind
from aws_orbit.services import cfn, eks, iam

if TYPE_CHECKING:
    from aws_orbit.manifest.team import TeamManifest

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST: Dict[str, Any] = {
    "apiVersion": "eksctl.io/v1alpha5",
    "kind": "ClusterConfig",
    "metadata": {"name": None, "region": None},
    "vpc": {"id": None, "cidr": None, "subnets": {"private": None, "public": None}},
    "iam": {"serviceRoleARN": None},
    "cloudWatch": {"clusterLogging": {"enableTypes": ["*"]}},
}


def create_nodegroup_structure(team: "TeamManifest", env_name: str) -> Dict[str, Any]:
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
        "labels": {"team": team.name, "orbit/compute-type": "ec2"},
        "tags": {"Env": f"orbit-{env_name}", "TeamSpace": team.name},
        "iam": {"instanceRoleARN": team.eks_nodegroup_role_arn},
        "securityGroups": {"attachIDs": [team.team_security_group_id]},
    }


def generate_manifest(manifest: Manifest, name: str, output_teams: bool = True) -> str:

    # Fill cluster wide configs
    MANIFEST["metadata"]["name"] = name
    MANIFEST["metadata"]["region"] = manifest.region
    MANIFEST["vpc"]["clusterEndpoints"] = {"publicAccess": True, "privateAccess": not manifest.internet_accessible}
    MANIFEST["vpc"]["id"] = manifest.vpc.vpc_id
    MANIFEST["vpc"]["cidr"] = manifest.vpc.cidr_block
    private_kind: SubnetKind = SubnetKind.private if manifest.internet_accessible else SubnetKind.isolated
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
            "tags": {"Env": "orbit"},
            "iam": {"instanceRoleARN": manifest.eks_env_nodegroup_role_arn},
        }
    )

    MANIFEST["fargateProfiles"] = [
        {
            "name": "fargate-default",
            "selectors": [
                {"namespace": "default"},
                {"namespace": "kube-system"},
            ],
        }
    ]

    MANIFEST["cloudWatch"] = {"clusterLogging": {"enableTypes": ["*"]}}

    _logger.debug("eksctl manifest:\n%s", pprint.pformat(MANIFEST))
    output_filename = f".orbit.out/{manifest.name}/eksctl/cluster.yaml"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, "w") as file:
        yaml.dump(MANIFEST, file, sort_keys=False)

    _logger.debug("output_filename: %s", output_filename)
    return output_filename


def fetch_cluster_data(manifest: Manifest, cluster_name: str) -> None:
    _logger.debug("Fetching Cluster data...")
    manifest.fetch_ssm()
    cluster_data = cast(Dict[str, Any], eks.describe_cluster(manifest=manifest, cluster_name=cluster_name))

    manifest.eks_oidc_provider = cluster_data["cluster"]["identity"]["oidc"]["issuer"].replace("https://", "")
    manifest.write_manifest_ssm()
    _logger.debug("Cluster data fetched successfully.")


def deploy_env(manifest: Manifest, eks_system_masters_roles_changes: Optional[ListChangeset]) -> None:
    stack_name: str = f"orbit-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    _logger.debug("Synthetizing the EKSCTL Environment manifest")
    output_filename = generate_manifest(manifest=manifest, name=stack_name, output_teams=False)
    cluster_name = f"orbit-{manifest.name}"

    if not cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name):
        _logger.debug("Deploying EKSCTL Environment resources")
        sh.run(f"eksctl create cluster -f {output_filename} --write-kubeconfig --verbose 4")

        username = f"orbit-{manifest.name}-admin"
        arn = f"arn:aws:iam::{manifest.account_id}:role/{username}"
        _logger.debug(f"Adding IAM Identity Mapping - Role: {arn}, Username: {username}, Group: system:masters")
        sh.run(
            f"eksctl create iamidentitymapping --cluster {cluster_name} --arn {arn} "
            f"--username {username} --group system:masters"
        )
    else:
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{manifest.name} --set-kubeconfig-context")

    fetch_cluster_data(manifest=manifest, cluster_name=cluster_name)

    if (
        iam.get_open_id_connect_provider(
            manifest=manifest, open_id_connect_provider_id=cast(str, manifest.eks_oidc_provider)
        )
        is None
    ):
        _logger.debug("Associating OpenID Connect Provider")
        sh.run(f"eksctl utils associate-iam-oidc-provider --cluster {cluster_name} --approve")
    else:
        _logger.debug("OpenID Connect Provider already associated")

    if eks_system_masters_roles_changes and eks_system_masters_roles_changes.added_values:
        for role in eks_system_masters_roles_changes.added_values:
            arn = f"arn:aws:iam::{manifest.account_id}:role/{role}"
            _logger.debug(f"Adding IAM Identity Mapping - Role: {arn}, Username: {role}, Group: system:masters")
            sh.run(
                f"eksctl create iamidentitymapping --cluster {cluster_name} --arn {arn} "
                f"--username {role} --group system:masters"
            )

    if eks_system_masters_roles_changes and eks_system_masters_roles_changes.removed_values:
        for role in eks_system_masters_roles_changes.removed_values:
            arn = f"arn:aws:iam::{manifest.account_id}:role/{role}"
            _logger.debug(f"Removing IAM Identity Mapping - Role: {arn}")
            sh.run(f"eksctl delete iamidentitymapping --cluster {cluster_name} --arn {arn} --all")

    _logger.debug("EKSCTL deployed")


def deploy_teams(manifest: Manifest) -> None:
    stack_name: str = f"orbit-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    _logger.debug("Synthetizing the EKSCTL Teams manifest")
    output_filename = generate_manifest(manifest=manifest, name=stack_name, output_teams=True)
    cluster_name = f"orbit-{manifest.name}"
    if cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name) and manifest.teams:
        subnet_kind = SubnetKind.private if manifest.internet_accessible else SubnetKind.isolated
        subnets = [s.subnet_id for s in manifest.vpc.subnets if s.kind == subnet_kind]
        for team in manifest.teams:
            eks.create_fargate_profile(
                manifest=manifest,
                profile_name=f"orbit-{manifest.name}-{team.name}",
                cluster_name=f"orbit-{manifest.name}",
                role_arn=cast(str, manifest.eks_fargate_profile_role_arn),
                subnets=subnets,
                namespace=team.name,
                selector_labels={"team": team.name, "orbit/compute-type": "fargate"},
            )

            username = f"orbit-{manifest.name}-{team.name}-runner"
            arn = f"arn:aws:iam::{manifest.account_id}:role/{username}"
            for line in sh.run_iterating(f"eksctl get iamidentitymapping --cluster {cluster_name} --arn {arn}"):
                if line == f'Error: no iamidentitymapping with arn "{arn}" found':
                    _logger.debug(
                        f"Adding IAM Identity Mapping - Role: {arn}, Username: {username}, Group: system:masters"
                    )
                    sh.run(
                        f"eksctl create iamidentitymapping --cluster {cluster_name} "
                        f"--arn {arn} --username {username} --group system:masters"
                    )
                    break
            else:
                _logger.debug(
                    f"Skipping existing IAM Identity Mapping - Role: {arn}, Username: {username}, Group: system:masters"
                )

        teams = ",".join([t.name for t in manifest.teams])
        _logger.debug("Deploying EKSCTL Teams resources")
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{manifest.name} --set-kubeconfig-context")
        sh.run(f"eksctl create nodegroup -f {output_filename} --include={teams} --verbose 4")

    _logger.debug("EKSCTL deployed")


def destroy_env(manifest: Manifest) -> None:
    stack_name: str = f"orbit-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{manifest.name} --set-kubeconfig-context")
        output_filename = generate_manifest(manifest=manifest, name=stack_name)
        sh.run(f"eksctl delete cluster -f {output_filename} --wait --verbose 4")
        _logger.debug("EKSCTL Envrionment destroyed")


def destroy_teams(manifest: Manifest) -> None:
    stack_name: str = f"orbit-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    cluster_name = f"orbit-{manifest.name}"
    if cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name) and manifest.teams:
        for team in manifest.teams:
            eks.delete_fargate_profile(
                manifest=manifest,
                profile_name=f"orbit-{manifest.name}-{team.name}",
                cluster_name=cluster_name,
            )

            username = f"orbit-{manifest.name}-{team.name}-runner"
            arn = f"arn:aws:iam::{manifest.account_id}:role/{username}"
            for line in sh.run_iterating(f"eksctl get iamidentitymapping --cluster {cluster_name} --arn {arn}"):
                if line == f'Error: no iamidentitymapping with arn "{arn}" found':
                    _logger.debug(f"Skipping non-existent IAM Identity Mapping - Role: {arn}")
                    break
            else:
                _logger.debug(f"Removing IAM Identity Mapping - Role: {arn}")
                sh.run(f"eksctl delete iamidentitymapping --cluster {cluster_name} --arn {arn}")

        teams = ",".join(
            [
                t.name
                for t in manifest.teams
                if eks.describe_nodegroup(manifest=manifest, cluster_name=cluster_name, nodegroup_name=t.name)
                is not None
            ]
        )
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{manifest.name} --set-kubeconfig-context")
        output_filename = generate_manifest(manifest=manifest, name=stack_name)
        if teams:
            sh.run(
                f"eksctl delete nodegroup -f {output_filename} --include={teams} "
                "--approve --wait --drain=false --verbose 4"
            )
        _logger.debug("EKSCTL Teams destroyed")


def destroy_team(manifest: Manifest, team_manifest: "TeamManifest") -> None:
    stack_name: str = f"orbit-{manifest.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    cluster_name = f"orbit-{manifest.name}"
    if cfn.does_stack_exist(manifest=manifest, stack_name=final_eks_stack_name):
        eks.delete_fargate_profile(
            manifest=manifest,
            profile_name=f"orbit-{manifest.name}-{team_manifest.name}",
            cluster_name=cluster_name,
        )

        username = f"orbit-{manifest.name}-{team_manifest.name}-runner"
        arn = f"arn:aws:iam::{manifest.account_id}:role/{username}"
        for line in sh.run_iterating(f"eksctl get iamidentitymapping --cluster {cluster_name} --arn {arn}"):
            if line == f'Error: no iamidentitymapping with arn "{arn}" found':
                _logger.debug(f"Skipping non-existent IAM Identity Mapping - Role: {arn}")
                break
        else:
            _logger.debug(f"Removing IAM Identity Mapping - Role: {arn}")
            sh.run(f"eksctl delete iamidentitymapping --cluster {cluster_name} --arn {arn}")

        if eks.describe_nodegroup(manifest=manifest, cluster_name=cluster_name, nodegroup_name=team_manifest.name):
            sh.run(
                f"eksctl delete nodegroup --cluster {cluster_name} --name {team_manifest.name} "
                "--update-auth-configmap --wait --drain=false --verbose 4"
            )
            _logger.debug("EKSCTL Team %s destroyed", team_manifest.name)
        else:
            _logger.debug("Team %s does not have nodegroup.", team_manifest.name)
