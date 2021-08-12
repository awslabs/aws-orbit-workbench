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

import concurrent.futures
import logging
import pprint
import re
import time
from typing import Any, Dict, List, Optional, cast

import botocore.exceptions

from aws_orbit import sh
from aws_orbit.models.context import Context, FoundationContext
from aws_orbit.remote_files.utils import get_k8s_context
from aws_orbit.services import cfn, efs, eks, elb, s3
from aws_orbit.utils import boto3_client, boto3_resource

_logger: logging.Logger = logging.getLogger(__name__)


def _detach_network_interface(nid: int, network_interface: Any) -> None:
    _logger.debug(f"Detaching NetworkInterface: {nid}.")
    network_interface.detach()
    _logger.debug(f"Reloading NetworkInterface: {nid}.")
    network_interface.reload()


def _network_interface(vpc_id: str) -> None:
    client = boto3_client("ec2")
    ec2 = boto3_resource("ec2")
    for i in client.describe_network_interfaces(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["NetworkInterfaces"]:
        try:
            network_interface = ec2.NetworkInterface(i["NetworkInterfaceId"])
            if "Interface for NAT Gateway" not in network_interface.description:
                _logger.debug(f"Forgotten NetworkInterface: {i['NetworkInterfaceId']}.")
                if network_interface.attachment is not None and network_interface.attachment["Status"] == "attached":
                    attempts: int = 0
                    while network_interface.attachment is None or network_interface.attachment["Status"] != "detached":
                        if attempts >= 10:
                            _logger.debug(
                                f"Ignoring NetworkInterface: {i['NetworkInterfaceId']} after 10 detach attempts."
                            )
                            break
                        _detach_network_interface(i["NetworkInterfaceId"], network_interface)
                        attempts += 1
                        time.sleep(3)
                    else:
                        network_interface.delete()
                        _logger.debug(f"NetWorkInterface {i['NetworkInterfaceId']} deleted.")
        except botocore.exceptions.ClientError as ex:
            error: Dict[str, Any] = ex.response["Error"]
            if "is currently in use" in error["Message"]:
                _logger.warning(f"Ignoring NetWorkInterface {i['NetworkInterfaceId']} because it stills in use.")
            elif "does not exist" in error["Message"]:
                _logger.warning(
                    f"Ignoring NetWorkInterface {i['NetworkInterfaceId']} because it does not exist anymore."
                )
            elif "You are not allowed to manage" in error["Message"]:
                _logger.warning(
                    f"Ignoring NetWorkInterface {i['NetworkInterfaceId']} because you are not allowed to manage."
                )
            elif "You do not have permission to access the specified resource" in error["Message"]:
                _logger.warning(
                    f"Ignoring NetWorkInterface {i['NetworkInterfaceId']} "
                    "because you do not have permission to access the specified resource."
                )
            else:
                raise


def delete_sec_group(sec_group: str) -> None:
    ec2 = boto3_resource("ec2")
    try:
        sgroup = ec2.SecurityGroup(sec_group)
        if sgroup.ip_permissions:
            sgroup.revoke_ingress(IpPermissions=sgroup.ip_permissions)
        try:
            sgroup.delete()
        except botocore.exceptions.ClientError as ex:
            error: Dict[str, Any] = ex.response["Error"]
            if f"resource {sec_group} has a dependent object" not in error["Message"]:
                raise
            time.sleep(60)
            _logger.warning(f"Waiting 60 seconds to have {sec_group} free of dependents.")
            sgroup.delete()
    except botocore.exceptions.ClientError as ex:
        error = ex.response["Error"]
        if f"The security group '{sec_group}' does not exist" not in error["Message"]:
            _logger.warning(f"Ignoring security group {sec_group} because it does not exist anymore.")
        elif f"resource {sec_group} has a dependent object" not in error["Message"]:
            _logger.warning(f"Ignoring security group {sec_group} because it has a dependent object")
        else:
            raise


def _security_group(vpc_id: str) -> None:
    client = boto3_client("ec2")
    sec_groups: List[str] = [
        s["GroupId"]
        for s in client.describe_security_groups()["SecurityGroups"]
        if s["VpcId"] == vpc_id and s["GroupName"] != "default"
    ]
    if sec_groups:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(sec_groups)) as executor:
            list(executor.map(delete_sec_group, sec_groups))


def _endpoints(vpc_id: str) -> None:
    client = boto3_client("ec2")
    paginator = client.get_paginator("describe_vpc_endpoints")
    response_iterator = paginator.paginate(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}], MaxResults=25)
    for resp in response_iterator:
        endpoint_ids: List[str] = []
        for endpoint in resp["VpcEndpoints"]:
            endpoint_id: str = cast(str, endpoint["VpcEndpointId"])
            _logger.debug("VPC endpoint %s found", endpoint_id)
            endpoint_ids.append(endpoint_id)
        _logger.debug("Deleting endpoints: %s", endpoint_ids)
        if endpoint_ids:
            resp = client.delete_vpc_endpoints(VpcEndpointIds=endpoint_ids)
            _logger.debug("resp:\n%s", pprint.pformat(resp))


def foundation_remaining_dependencies(context: "FoundationContext", vpc_id: Optional[str] = None) -> None:
    efs.delete_env_filesystems(env_name=context.name)
    if context.scratch_bucket_arn:
        scratch_bucket: str = context.scratch_bucket_arn.split(":::")[1]
        try:
            s3.delete_bucket(bucket=scratch_bucket)
        except Exception as ex:
            _logger.debug("Skipping Team Scratch Bucket deletion. Cause: %s", ex)
    if vpc_id is None:
        if context.networking.vpc_id is None:
            _logger.debug("Skipping _cleanup_remaining_dependencies() because manifest.vpc.vpc_id is None!")
            return None
        vpc_id = context.networking.vpc_id
    elb.delete_load_balancers(env_name=context.name)
    _endpoints(vpc_id=vpc_id)
    _network_interface(vpc_id=vpc_id)
    _security_group(vpc_id=vpc_id)


def foundation_remaining_dependencies_contextless(env_name: str, vpc_id: Optional[str] = None) -> None:
    efs.delete_env_filesystems(env_name=env_name)
    if vpc_id:
        elb.delete_load_balancers(env_name=env_name)
        _endpoints(vpc_id=vpc_id)
        _network_interface(vpc_id=vpc_id)
        _security_group(vpc_id=vpc_id)


def delete_cert_from_iam(context: "FoundationContext") -> None:
    iam_client = boto3_client("iam")
    cert_name = f"{context.name}-{context.region}"
    try:
        iam_client.delete_server_certificate(ServerCertificateName=cert_name)
    except botocore.exceptions.ClientError as ex:
        if ex.response["Error"]["Code"] == "NoSuchEntity":
            pass
        else:
            raise ex


def delete_kubeflow_roles(env_stack_name: str, region: str, account_id: str) -> None:
    iam_client = boto3_client("iam")

    roles = iam_client.list_roles()

    regex_comp = re.compile(rf"kf-.*-{region}-{env_stack_name}")

    for role in roles.get("Roles"):
        role_name = role.get("RoleName")

        if regex_comp.fullmatch(role_name):
            _logger.info(f"Removing role {role_name} - checking for attached policies")
            role_policies = iam_client.list_role_policies(RoleName=role_name).get("PolicyNames")

            for policy_name in role_policies:
                try:
                    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
                    iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
                    _logger.info(f"Detached policy {policy_name}")
                except iam_client.exceptions.NoSuchEntityException:
                    _logger.error("No such policy")
                except iam_client.exceptions.UnmodifiableEntityException:
                    _logger.error("Policy is unmodifiable")
                except iam_client.exceptions.ServiceFailureException as err:
                    _logger.error(f"Service error: {err}")

                try:
                    policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
                    iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                    _logger.info(f"Deleted in-policy {policy_name}")
                except iam_client.exceptions.NoSuchEntityException:
                    _logger.error("No such policy")
                except iam_client.exceptions.UnmodifiableEntityException:
                    _logger.error("Policy is unmodifiable")
                except iam_client.exceptions.ServiceFailureException as err:
                    _logger.error(f"Service error: {err}")

            try:
                iam_client.delete_role(RoleName=role_name)
                _logger.info(f"Removed role {role_name}")
            except iam_client.exceptions.NoSuchEntityException:
                _logger.error("No such role")
            except iam_client.exceptions.UnmodifiableEntityException:
                _logger.error("Role is unmodifiable")
            except iam_client.exceptions.ConcurrentModificationException:
                _logger.error("Error. There were concurrent operations in modifying this role")
            except iam_client.exceptions.ServiceFailureException as err:
                _logger.error(f"Service error: {err}")


# Removes ELB since the listener is attached to the target group
# and the target group can't be removed with a listener attached
def delete_target_group(cluster_name: str) -> None:
    elb_client = boto3_client("elbv2")

    target_groups = elb_client.describe_target_groups()

    for target_group in target_groups.get("TargetGroups", []):
        target_group_arn = target_group.get("TargetGroupArn")

        target_group_tags = elb_client.describe_tags(ResourceArns=[target_group_arn])

        for tag in target_group_tags.get("TagDescriptions", [{}])[0].get("Tags", []):
            if tag.get("Key") == "ingress.k8s.aws/cluster":
                if tag.get("Value") == cluster_name:
                    elbs = target_group.get("LoadBalancerArns")

                    for _elb in elbs:
                        try:
                            _logger.info(f"Removing ELB: {_elb}")
                            elb_client.delete_load_balancer(LoadBalancerArn=_elb)
                            time.sleep(10)
                            _logger.info("ELB deleted")
                        except elb_client.exceptions.LoadBalancerNotFoundException as err:
                            _logger.warning(f"ELB not found: {err}")
                        except elb_client.exceptions.OperationNotPermittedException as err:
                            _logger.error(err)
                        except elb_client.exceptions.ResourceInUseException as err:
                            _logger.error(f"Resource in use: {err}")

                    target_group_name = target_group.get("Name")
                    try:
                        _logger.info(f"Removing target group: {target_group_name}")
                        elb_client.delete_target_group(TargetGroupArn=target_group_arn)
                        _logger.info("Target group deleted")
                    except elb_client.exceptions.ResourceInUseException as err:
                        _logger.error(f"Target in use: {err}")


def delete_elb_security_group(cluster_name: str) -> None:
    ec2_client = boto3_client("ec2")

    security_groups = ec2_client.describe_security_groups(
        Filters=[
            {"Name": "tag:ingress.k8s.aws/resource", "Values": ["ManagedLBSecurityGroup"]},
            {"Name": "tag:kubernetes.io/cluster-name", "Values": [cluster_name]},
        ]
    )

    for security_group in security_groups.get("SecurityGroups", []):
        security_group_id = security_group.get("GroupId")

        try:
            _logger.info("Removing Security Group: %s", security_group_id)
            ec2_client.delete_security_group(GroupId=security_group_id)
            _logger.info("Security Group deleted")
        except Exception:
            _logger.exception("Failed to delete Security Group")


def delete_system_fargate_profile(context: Context) -> None:
    cluster_name = f"orbit-{context.name}"
    eks_stack_name = f"eksctl-{cluster_name}-cluster"
    if cfn.does_stack_exist(stack_name=eks_stack_name) and not context.networking.data.internet_accessible:
        fargate_profile = f"orbit-{context.name}-system"
        _logger.info(f"Deleting Fargate Profile: {fargate_profile}")
        eks.delete_fargate_profile(
            profile_name=fargate_profile,
            cluster_name=cluster_name,
        )
    else:
        _logger.info("Skipping Fargate Profile Deletion")


def delete_istio_ingress(context: Context) -> None:
    try:
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        k8s_context = get_k8s_context(context=context)
        _logger.debug("k8s_context: %s", k8s_context)

        _logger.info("Deleting istio-ingress")
        sh.run(f"kubectl delete ingress -n istio-system --context {k8s_context} --wait istio-ingress")
        time.sleep(30)
        _logger.info("Deleted istio-ingress")
    except:  # noqa: E722
        _logger.exception("Failed to delete istio-ingress")
