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
import re
from typing import Any, Dict, List, Optional, cast

import yaml

from aws_orbit import sh
from aws_orbit.models.changeset import Changeset, ListChangeset
from aws_orbit.models.context import Context, ContextSerDe, TeamContext
from aws_orbit.models.manifest import ManagedNodeGroupManifest
from aws_orbit.services import autoscaling, cfn, ec2, eks, iam
from aws_orbit.services.ec2 import IpPermission, UserIdGroupPair

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST: Dict[str, Any] = {
    "apiVersion": "eksctl.io/v1alpha5",
    "kind": "ClusterConfig",
    "metadata": {"name": None, "region": None},
    "vpc": {"id": None, "cidr": None, "subnets": {"private": {}, "public": {}}},
    "iam": {"serviceRoleARN": None},
    "cloudWatch": {"clusterLogging": {"enableTypes": ["*"]}},
}


def create_nodegroup_structure(context: "Context", nodegroup: ManagedNodeGroupManifest) -> Dict[str, Any]:
    labels = {"orbit/node-group": nodegroup.name, "orbit/usage": "teams", "orbit/node-type": "ec2"}
    labels.update(nodegroup.labels)

    # Extra label for gpu instance types
    if re.match("^p[2-9]|^g[3-9]", nodegroup.instance_type):
        if nodegroup.enable_virtual_gpu:
            labels["k8s.amazonaws.com/accelerator"] = "vgpu"
        else:
            labels["k8s.amazonaws.com/accelerator"] = "gpu"

    tags = {f"k8s.io/cluster-autoscaler/node-template/label/{k}": v for k, v in labels.items()}
    tags["Env"] = f"orbit-{context.name}"

    return {
        "name": nodegroup.name,
        "privateNetworking": True,
        "instanceType": nodegroup.instance_type,
        "minSize": 1 if nodegroup.nodes_num_min < 1 else nodegroup.nodes_num_min,
        "desiredCapacity": 1 if nodegroup.nodes_num_desired < 1 else nodegroup.nodes_num_desired,
        "maxSize": nodegroup.nodes_num_max,
        "volumeSize": nodegroup.local_storage_size,
        "ssh": {"allow": False},
        "labels": labels,
        "tags": tags,
        "iam": {"instanceRoleARN": context.eks_env_nodegroup_role_arn},
    }


def generate_manifest(context: "Context", name: str, nodegroups: Optional[List[ManagedNodeGroupManifest]]) -> str:
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

    labels = {"orbit/node-group": "env", "orbit/usage": "reserved"}
    tags = tags = {f"k8s.io/cluster-autoscaler/node-template/label/{k}": v for k, v in labels.items()}
    tags["Env"] = f"orbit-{context.name}"

    # Env
    MANIFEST["managedNodeGroups"].append(
        {
            "name": "env",
            "privateNetworking": True,
            "instanceType": "t3a.xlarge",
            "minSize": 1,
            "desiredCapacity": 2,
            "maxSize": 4,
            "volumeSize": 64,
            "ssh": {"allow": False},
            "labels": labels,
            "tags": tags,
            "iam": {"instanceRoleARN": context.eks_env_nodegroup_role_arn},
        }
    )

    # Fill nodegroups configs
    if nodegroups:
        for nodegroup in nodegroups:
            MANIFEST["managedNodeGroups"].append(create_nodegroup_structure(context=context, nodegroup=nodegroup))

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


def map_iam_identities(
    context: Context, cluster_name: str, eks_system_masters_roles_changes: Optional[ListChangeset]
) -> None:
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
                    cast(List[str], context.eks_system_masters_roles).append(role)
                    ContextSerDe.dump_context_to_ssm(context=context)
                    break
            else:
                _logger.debug(f"Skip adding existing IAM Identity Mapping - Role: {arn}")

    if eks_system_masters_roles_changes and eks_system_masters_roles_changes.removed_values:
        for role in eks_system_masters_roles_changes.removed_values:
            arn = f"arn:aws:iam::{context.account_id}:role/{role}"
            for line in sh.run_iterating(f"eksctl get iamidentitymapping --cluster {cluster_name} --arn {arn}"):
                if line.startswith("Error: no iamidentitymapping with arn"):
                    _logger.debug(f"Skip removing nonexisting IAM Identity Mapping - Role: {arn}")
                    break
            else:
                _logger.debug(f"Removing IAM Identity Mapping - Role: {arn}")
                sh.run(f"eksctl delete iamidentitymapping --cluster {cluster_name} --arn {arn} --all")
                cast(List[str], context.eks_system_masters_roles).remove(role)
                ContextSerDe.dump_context_to_ssm(context=context)


def create_cluster_autoscaler_service_account(context: Context) -> None:
    policy_arn = f"arn:aws:iam::{context.account_id}:policy/orbit-{context.name}-cluster-autoscaler-policy"
    _logger.debug(f"Creating ClusterAutoscaler ServiceAccount with Policy ARN: {policy_arn}")
    sh.run(
        f"eksctl create iamserviceaccount --cluster=orbit-{context.name} --namespace=kube-system "
        f"--name=cluster-autoscaler --attach-policy-arn={policy_arn} --override-existing-serviceaccounts "
        "--approve"
    )


def get_pod_to_cluster_rules(group_id: str) -> List[IpPermission]:
    return [
        IpPermission(
            from_port=53,
            to_port=53,
            ip_protocol="tcp",
            user_id_group_pairs=[UserIdGroupPair(description="DNS Lookup from Pod", group_id=group_id)],
        ),
        IpPermission(
            from_port=53,
            to_port=53,
            ip_protocol="udp",
            user_id_group_pairs=[UserIdGroupPair(description="DNS Lookup from Pod", group_id=group_id)],
        ),
        IpPermission(
            from_port=443,
            to_port=443,
            ip_protocol="tcp",
            user_id_group_pairs=[UserIdGroupPair(description="Kubernetes API from Pod", group_id=group_id)],
        ),
        IpPermission(
            from_port=10250,
            to_port=10250,
            ip_protocol="tcp",
            user_id_group_pairs=[UserIdGroupPair(description="Kubelet from Pod", group_id=group_id)],
        ),
    ]


def get_cluster_to_pod_rules(group_id: str) -> List[IpPermission]:
    return [
        IpPermission(
            from_port=-1,
            to_port=-1,
            ip_protocol="-1",
            user_id_group_pairs=[UserIdGroupPair(description="All from Cluster", group_id=group_id)],
        )
    ]


def authorize_cluster_pod_security_group(context: Context) -> None:
    # Authorize Pods to access Cluster
    ec2.authorize_security_group_ingress(
        group_id=cast(str, context.cluster_sg_id),
        ip_permissions=get_pod_to_cluster_rules(cast(str, context.cluster_pod_sg_id)),
    )
    ec2.authorize_security_group_egress(
        group_id=cast(str, context.cluster_pod_sg_id),
        ip_permissions=get_pod_to_cluster_rules(cast(str, context.cluster_sg_id)),
    )

    # Authorize Cluster to access Pods
    ec2.authorize_security_group_ingress(
        group_id=cast(str, context.cluster_pod_sg_id),
        ip_permissions=get_cluster_to_pod_rules(cast(str, context.cluster_sg_id)),
    )
    ec2.authorize_security_group_egress(
        group_id=cast(str, context.cluster_sg_id),
        ip_permissions=get_cluster_to_pod_rules(cast(str, context.cluster_pod_sg_id)),
    )


def revoke_cluster_pod_security_group(context: Context) -> None:
    # Authorize Pods to access Cluster
    ec2.revoke_security_group_ingress(
        group_id=cast(str, context.cluster_sg_id),
        ip_permissions=get_pod_to_cluster_rules(cast(str, context.cluster_pod_sg_id)),
    )
    ec2.revoke_security_group_egress(
        group_id=cast(str, context.cluster_pod_sg_id),
        ip_permissions=get_pod_to_cluster_rules(cast(str, context.cluster_sg_id)),
    )

    # Authorize Cluster to access Pods
    ec2.revoke_security_group_ingress(
        group_id=cast(str, context.cluster_pod_sg_id),
        ip_permissions=get_cluster_to_pod_rules(cast(str, context.cluster_sg_id)),
    )
    ec2.revoke_security_group_egress(
        group_id=cast(str, context.cluster_sg_id),
        ip_permissions=get_cluster_to_pod_rules(cast(str, context.cluster_pod_sg_id)),
    )


def fetch_cluster_data(context: "Context", cluster_name: str) -> None:
    _logger.debug("Fetching Cluster data...")
    cluster_data = cast(Dict[str, Any], eks.describe_cluster(cluster_name=cluster_name))

    context.eks_oidc_provider = cluster_data["cluster"]["identity"]["oidc"]["issuer"].replace("https://", "")
    context.cluster_sg_id = cluster_data["cluster"]["resourcesVpcConfig"]["clusterSecurityGroupId"]
    ContextSerDe.dump_context_to_ssm(context=context)
    _logger.debug("Cluster data fetched successfully.")


def deploy_env(context: "Context", changeset: Optional[Changeset]) -> None:
    stack_name: str = f"orbit-{context.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    _logger.debug("Synthetizing the EKSCTL Environment manifest")
    cluster_name = f"orbit-{context.name}"

    if cfn.does_stack_exist(stack_name=final_eks_stack_name) is False:

        requested_nodegroups = (
            changeset.managed_nodegroups_changeset.added_nodegroups
            if changeset and changeset.managed_nodegroups_changeset
            else []
        )
        _logger.debug(f"requested nodegroups: {[n.name for n in requested_nodegroups]}")

        output_filename = generate_manifest(context=context, name=stack_name, nodegroups=requested_nodegroups)

        _logger.debug("Deploying EKSCTL Environment resources")
        sh.run(
            f"eksctl create cluster -f {output_filename} --install-nvidia-plugin=false "
            "--write-kubeconfig --verbose 4"
        )

        username = f"orbit-{context.name}-admin"
        arn = f"arn:aws:iam::{context.account_id}:role/{username}"
        _logger.debug(f"Adding IAM Identity Mapping - Role: {arn}, Username: {username}, Group: system:masters")
        sh.run(
            f"eksctl create iamidentitymapping --cluster {cluster_name} --arn {arn} "
            f"--username {username} --group system:masters"
        )
        context.managed_nodegroups = requested_nodegroups

        for ng in requested_nodegroups:
            if ng.nodes_num_desired < 1 or ng.nodes_num_min < 1:
                _logger.debug(f"Reducing AutoScaling capacity for newly create NodeGroup: {ng.name}")
                autoscaling.update_nodegroup_autoscaling_group(
                    cluster_name=f"orbit-{context.name}", nodegroup_manifest=ng
                )

        ContextSerDe.dump_context_to_ssm(context=context)
    else:

        current_nodegroups = context.managed_nodegroups
        _logger.debug(f"current nodegroups: {[n.name for n in current_nodegroups]}")

        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        if changeset and changeset.managed_nodegroups_changeset:
            if changeset.managed_nodegroups_changeset.added_nodegroups:
                output_filename = generate_manifest(
                    context=context, name=stack_name, nodegroups=changeset.managed_nodegroups_changeset.added_nodegroups
                )
                nodegroups = [
                    ng.name
                    for ng in changeset.managed_nodegroups_changeset.added_nodegroups
                    if not eks.describe_nodegroup(cluster_name=cluster_name, nodegroup_name=ng.name)
                ]
                _logger.debug("Creating ManagedNodeGroups: %s", nodegroups)
                sh.run(f"eksctl create nodegroup -f {output_filename} --include={','.join(nodegroups)} --verbose 4")
                current_nodegroups.extend(
                    [ng for ng in changeset.managed_nodegroups_changeset.added_nodegroups if ng.name in nodegroups]
                )
                context.managed_nodegroups = current_nodegroups
                ContextSerDe.dump_context_to_ssm(context=context)

            if changeset.managed_nodegroups_changeset.removed_nodegroups:
                output_filename = generate_manifest(
                    context=context,
                    name=stack_name,
                    nodegroups=changeset.managed_nodegroups_changeset.removed_nodegroups,
                )
                nodegroups = [
                    ng.name
                    for ng in changeset.managed_nodegroups_changeset.removed_nodegroups
                    if eks.describe_nodegroup(cluster_name=cluster_name, nodegroup_name=ng.name)
                ]
                _logger.debug("Deleting ManagedNodeGroups: %s", nodegroups)
                sh.run(
                    f"eksctl delete nodegroup -f {output_filename} --include={','.join(nodegroups)} "
                    "--approve --wait --drain=false --verbose 4"
                )
                context.managed_nodegroups = [ng for ng in current_nodegroups if ng.name not in nodegroups]
                ContextSerDe.dump_context_to_ssm(context=context)

            if changeset.managed_nodegroups_changeset.modified_nodegroups:
                for ng in changeset.managed_nodegroups_changeset.modified_nodegroups:
                    autoscaling.update_nodegroup_autoscaling_group(
                        cluster_name=f"orbit-{context.name}", nodegroup_manifest=ng
                    )

    eks_system_masters_changeset = (
        changeset.eks_system_masters_roles_changeset
        if changeset and changeset.eks_system_masters_roles_changeset
        else None
    )
    map_iam_identities(
        context=context,
        cluster_name=cluster_name,
        eks_system_masters_roles_changes=eks_system_masters_changeset,
    )

    associate_open_id_connect_provider(context=context, cluster_name=cluster_name)
    fetch_cluster_data(context=context, cluster_name=cluster_name)
    authorize_cluster_pod_security_group(context=context)

    iam.add_assume_role_statement(
        role_name=f"orbit-{context.name}-cluster-autoscaler-role",
        statement={
            "Effect": "Allow",
            "Principal": {"Federated": f"arn:aws:iam::{context.account_id}:oidc-provider/{context.eks_oidc_provider}"},
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringLike": {
                    f"{context.eks_oidc_provider}:sub": "system:serviceaccount:kube-system:cluster-autoscaler"
                }
            },
        },
    )

    _logger.debug("EKSCTL deployed")


def deploy_team(context: "Context", team_context: "TeamContext") -> None:
    stack_name: str = f"orbit-{context.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    _logger.debug("Synthetizing the EKSCTL Teams manifest")
    cluster_name = f"orbit-{context.name}"
    if cfn.does_stack_exist(stack_name=final_eks_stack_name) and context.teams:
        if team_context.fargate:
            subnets = (
                context.networking.private_subnets
                if context.networking.data.internet_accessible
                else context.networking.isolated_subnets
            )
            subnets_ids = [s.subnet_id for s in subnets]

            eks.create_fargate_profile(
                profile_name=f"orbit-{context.name}-{team_context.name}",
                cluster_name=f"orbit-{context.name}",
                role_arn=cast(str, context.eks_fargate_profile_role_arn),
                subnets=subnets_ids,
                namespace=team_context.name,
                selector_labels={"team": team_context.name, "orbit/node-type": "fargate"},
            )

        username = f"orbit-{context.name}-{team_context.name}-runner"
        arn = f"arn:aws:iam::{context.account_id}:role/{username}"
        for line in sh.run_iterating(f"eksctl get iamidentitymapping --cluster {cluster_name} --arn {arn}"):
            if line == f'Error: no iamidentitymapping with arn "{arn}" found':
                _logger.debug(f"Adding IAM Identity Mapping - Role: {arn}, Username: {username}, Group: system:masters")
                sh.run(
                    f"eksctl create iamidentitymapping --cluster {cluster_name} "
                    f"--arn {arn} --username {username} --group system:masters"
                )
                break
        else:
            _logger.debug(
                f"Skipping existing IAM Identity Mapping - Role: {arn}, Username: {username}, Group: system:masters"
            )


def destroy_env(context: "Context") -> None:
    stack_name: str = f"orbit-{context.name}"
    final_eks_stack_name: str = f"eksctl-{stack_name}-cluster"
    _logger.debug("EKSCTL stack name: %s", final_eks_stack_name)
    if cfn.does_stack_exist(stack_name=final_eks_stack_name):
        revoke_cluster_pod_security_group(context=context)

        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        output_filename = generate_manifest(context=context, name=stack_name, nodegroups=context.managed_nodegroups)
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
