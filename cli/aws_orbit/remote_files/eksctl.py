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
from aws_orbit.models.context import dump_context_to_ssm
from aws_orbit.services import cfn, eks, iam

if TYPE_CHECKING:
    from aws_orbit.models.changeset import ListChangeset
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST: Dict[str, Any] = {
    "apiVersion": "eksctl.io/v1alpha5",
    "kind": "ClusterConfig",
    "metadata": {"name": None, "region": None},
    "vpc": {"id": None, "cidr": None, "subnets": {"private": {}, "public": {}}},
    "iam": {"serviceRoleARN": None},
    "cloudWatch": {"clusterLogging": {"enableTypes": ["*"]}},
}


def create_nodegroup_structure(context: "Context", team: "TeamContext", env_name: str) -> Dict[str, Any]:
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
        "iam": {"instanceRoleARN": context.eks_env_nodegroup_role_arn},
    }


def generate_manifest(context: "Context", name: str, output_teams: bool = True) -> str:
    internet: bool = context.networking.data.internet_accessible

    # Fill cluster wide configs
    MANIFEST["metadata"]["name"] = name
    MANIFEST["metadata"]["region"] = context.region
    MANIFEST["vpc"]["clusterEndpoints"] = {"publicAccess": True, "privateAccess": not internet}
    if context.networking.vpc_id is None:
        raise ValueError("context.networking.vpc_id is None!")
    MANIFEST["vpc"]["id"] = context.networking.vpc_id
    if context.networking.vpc_cidr_block is None:
        raise ValueError("context.networking.vpc_cidr_block is None!")
    MANIFEST["vpc"]["cidr"] = context.networking.vpc_cidr_block

    for subnet in context.networking.public_subnets:
        if subnet.availability_zone is None:
            raise ValueError("subnet.availability_zone is None for %s!", subnet.subnet_id)
        if subnet.cidr_block is None:
            raise ValueError("subnet.cidr_block is None for %s!", subnet.subnet_id)
        MANIFEST["vpc"]["subnets"]["public"][subnet.availability_zone] = {
            "id": subnet.subnet_id,
            "cidr": subnet.cidr_block,
        }

    private_subnets = context.networking.private_subnets if internet else context.networking.isolated_subnets
    for subnet in private_subnets:
        if subnet.availability_zone is None:
            raise ValueError("subnet.availability_zone is None for %s!", subnet.subnet_id)
        if subnet.cidr_block is None:
            raise ValueError("subnet.cidr_block is None for %s!", subnet.subnet_id)
        MANIFEST["vpc"]["subnets"]["private"][subnet.availability_zone] = {
            "id": subnet.subnet_id,
            "cidr": subnet.cidr_block,
        }

    MANIFEST["iam"]["serviceRoleARN"] = context.eks_cluster_role_arn
    MANIFEST["managedNodeGroups"] = []

    # Fill nodegroups configs
    if context.teams and output_teams:
        for team in context.teams:
            MANIFEST["managedNodeGroups"].append(
                create_nodegroup_structure(context=context, team=team, env_name=context.name)
            )

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
            "iam": {"instanceRoleARN": context.eks_env_nodegroup_role_arn},
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
    output_filename = f".orbit.out/{context.name}/eksctl/cluster.yaml"
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, "w") as file:
        yaml.dump(MANIFEST, file, sort_keys=False)

    _logger.debug("output_filename: %s", output_filename)
    return output_filename


def associate_open_id_connect_provider(context: Context, cluster_name: str) -> None:
    if (
        iam.get_open_id_connect_provider(
            account_id=context.account_id, open_id_connect_provider_id=cast(str, context.eks_oidc_provider)
        )
        is None
    ):
        _logger.debug("Associating OpenID Connect Provider")
        sh.run(f"eksctl utils associate-iam-oidc-provider --cluster {cluster_name} --approve")
    else:
        _logger.debug("OpenID Connect Provider already associated")



def map_iam_identities(context: Context, cluster_name: str, eks_system_masters_roles_changes: Optional["ListChangeset"]) -> None:
    if eks_system_masters_roles_changes and eks_system_masters_roles_changes.added_values:
        for role in eks_system_masters_roles_changes.added_values:
            if iam.get_role(role) is None:
                _logger.debug(f"Skipping nonexisting IAM Role: {role}")
                continue

            arn = f"arn:aws:iam::{context.account_id}:role/{role}"
            for line in sh.run_iterating(f"eksctl get iamidentitymapping --cluster {cluster_name} --arn {arn}"):
                if line.startswith("Error: no iamidentitymapping with arn"):
                    _logger.debug(f"Adding IAM Identity Mapping - Role: {arn}, Username: {role}, Group: system:masters")
                    sh.run(
                        f"eksctl create iamidentitymapping --cluster {cluster_name} --arn {arn} "
                        f"--username {role} --group system:masters"
                    )
                    break
            else:
                _logger.debug(f"Skipping existing IAM Identity Mapping - Role: {arn}")

    if eks_system_masters_roles_changes and eks_system_masters_roles_changes.removed_values:
        for role in eks_system_masters_roles_changes.removed_values:
            arn = f"arn:aws:iam::{context.account_id}:role/{role}"
            _logger.debug(f"Removing IAM Identity Mapping - Role: {arn}")
            sh.run(f"eksctl delete iamidentitymapping --cluster {cluster_name} --arn {arn} --all")


def authorize_cluster_pod_security_group(context: Context): -> None:




def fetch_cluster_data(context: "Context", cluster_name: str) -> None:
    _logger.debug("Fetching Cluster data...")
    cluster_data = cast(Dict[str, Any], eks.describe_cluster(cluster_name=cluster_name))

    context.eks_oidc_provider = cluster_data["cluster"]["identity"]["oidc"]["issuer"].replace("https://", "")
    context.cluster_sg_id = cluster_data["cluster"]["resourcesVpcConfig"]["clusterSecurityGroupId"]
    dump_context_to_ssm(context=context)
    _logger.debug("Cluster data fetched successfully.")


def deploy_env(context: "Context", eks_system_masters_roles_changes: Optional["ListChangeset"]) -> None:
    stack_name: str = f"orbit-{context.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    _logger.debug("Synthetizing the EKSCTL Environment manifest")
    output_filename = generate_manifest(context=context, name=stack_name, output_teams=False)
    cluster_name = f"orbit-{context.name}"

    if not cfn.does_stack_exist(stack_name=final_eks_stack_name):
        _logger.debug("Deploying EKSCTL Environment resources")
        sh.run(f"eksctl create cluster -f {output_filename} --write-kubeconfig --verbose 4")

        username = f"orbit-{context.name}-admin"
        arn = f"arn:aws:iam::{context.account_id}:role/{username}"
        _logger.debug(f"Adding IAM Identity Mapping - Role: {arn}, Username: {username}, Group: system:masters")
        sh.run(
            f"eksctl create iamidentitymapping --cluster {cluster_name} --arn {arn} "
            f"--username {username} --group system:masters"
        )
    else:
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")

    fetch_cluster_data(context=context, cluster_name=cluster_name)
    associate_open_id_connect_provider(context=context, cluster_name=cluster_name)
    map_iam_identities(context=context, cluster_name=cluster_name, eks_system_masters_roles_changes=eks_system_masters_roles_changes)
    authorize_cluster_pod_security_group(context=context)

    _logger.debug("EKSCTL deployed")


def deploy_teams(context: "Context") -> None:
    stack_name: str = f"orbit-{context.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    _logger.debug("Synthetizing the EKSCTL Teams manifest")
    output_filename = generate_manifest(context=context, name=stack_name, output_teams=True)
    cluster_name = f"orbit-{context.name}"
    if cfn.does_stack_exist(stack_name=final_eks_stack_name) and context.teams:
        subnets = (
            context.networking.private_subnets
            if context.networking.data.internet_accessible
            else context.networking.isolated_subnets
        )
        subnets_ids = [s.subnet_id for s in subnets]
        for team in context.teams:
            eks.create_fargate_profile(
                profile_name=f"orbit-{context.name}-{team.name}",
                cluster_name=f"orbit-{context.name}",
                role_arn=cast(str, context.eks_fargate_profile_role_arn),
                subnets=subnets_ids,
                namespace=team.name,
                selector_labels={"team": team.name, "orbit/compute-type": "fargate"},
            )

            username = f"orbit-{context.name}-{team.name}-runner"
            arn = f"arn:aws:iam::{context.account_id}:role/{username}"
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

        teams = ",".join([t.name for t in context.teams])
        _logger.debug("Deploying EKSCTL Teams resources")
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        sh.run(f"eksctl create nodegroup -f {output_filename} --include={teams} --verbose 4")

    _logger.debug("EKSCTL deployed")


def destroy_env(context: "Context") -> None:
    stack_name: str = f"orbit-{context.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    if cfn.does_stack_exist(stack_name=final_eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        output_filename = generate_manifest(context=context, name=stack_name)
        sh.run(f"eksctl delete cluster -f {output_filename} --wait --verbose 4")
        _logger.debug("EKSCTL Envrionment destroyed")


def destroy_teams(context: "Context") -> None:
    stack_name: str = f"orbit-{context.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    cluster_name = f"orbit-{context.name}"
    if cfn.does_stack_exist(stack_name=final_eks_stack_name) and context.teams:
        for team in context.teams:
            eks.delete_fargate_profile(
                profile_name=f"orbit-{context.name}-{team.name}",
                cluster_name=cluster_name,
            )

            username = f"orbit-{context.name}-{team.name}-runner"
            arn = f"arn:aws:iam::{context.account_id}:role/{username}"
            for line in sh.run_iterating(f"eksctl get iamidentitymapping --cluster {cluster_name} --arn {arn}"):
                if line == f'Error: no iamidentitymapping with arn "{arn}" found':
                    _logger.debug(f"Skipping non-existent IAM Identity Mapping - Role: {arn}")
                    break
            else:
                _logger.debug(f"Removing IAM Identity Mapping - Role: {arn}")
                sh.run(f"eksctl delete iamidentitymapping --cluster {cluster_name} --arn {arn}")

        teams_names = ",".join(
            [
                t.name
                for t in context.teams
                if eks.describe_nodegroup(cluster_name=cluster_name, nodegroup_name=t.name) is not None
            ]
        )
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        output_filename = generate_manifest(context=context, name=stack_name)
        if teams_names:
            sh.run(
                f"eksctl delete nodegroup -f {output_filename} --include={teams_names} "
                "--approve --wait --drain=false --verbose 4"
            )
        _logger.debug("EKSCTL Teams destroyed")


def destroy_team(context: "Context", team_context: "TeamContext") -> None:
    stack_name: str = f"orbit-{context.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    cluster_name = f"orbit-{context.name}"
    if cfn.does_stack_exist(stack_name=final_eks_stack_name):
        eks.delete_fargate_profile(
            profile_name=f"orbit-{context.name}-{team_context.name}",
            cluster_name=cluster_name,
        )

        username = f"orbit-{context.name}-{team_context.name}-runner"
        arn = f"arn:aws:iam::{context.account_id}:role/{username}"
        for line in sh.run_iterating(f"eksctl get iamidentitymapping --cluster {cluster_name} --arn {arn}"):
            if line == f'Error: no iamidentitymapping with arn "{arn}" found':
                _logger.debug(f"Skipping non-existent IAM Identity Mapping - Role: {arn}")
                break
        else:
            _logger.debug(f"Removing IAM Identity Mapping - Role: {arn}")
            sh.run(f"eksctl delete iamidentitymapping --cluster {cluster_name} --arn {arn}")

        if eks.describe_nodegroup(cluster_name=cluster_name, nodegroup_name=team_context.name):
            sh.run(
                f"eksctl delete nodegroup --cluster {cluster_name} --name {team_context.name} "
                "--update-auth-configmap --wait --drain=false --verbose 4"
            )
            _logger.debug("EKSCTL Team %s destroyed", team_context.name)
        else:
            _logger.debug("Team %s does not have nodegroup.", team_context.name)
