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
import time
from itertools import repeat
from typing import Any, Dict, List

import botocore.exceptions

from datamaker_cli import cdk, plugins
from datamaker_cli.manifest import Manifest
from datamaker_cli.services import cfn

_logger: logging.Logger = logging.getLogger(__name__)


def _network_interface(manifest: Manifest, vpc_id: str) -> None:
    client = manifest.boto3_client("ec2")
    ec2 = manifest.boto3_resource("ec2")
    for i in client.describe_network_interfaces(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["NetworkInterfaces"]:
        try:
            network_interface = ec2.NetworkInterface(i["NetworkInterfaceId"])
            if "Interface for NAT Gateway" not in network_interface.description:
                _logger.debug(f"Forgotten NetworkInterface: {i['NetworkInterfaceId']}.")
                if network_interface.attachment is not None and network_interface.attachment["Status"] == "attached":
                    network_interface.detach()
                    network_interface.reload()
                    while network_interface.attachment is None or network_interface.attachment["Status"] != "detached":
                        time.sleep(1)
                        network_interface.reload()
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
            else:
                raise


def delete_sec_group(manifest: Manifest, sec_group: str) -> None:
    ec2 = manifest.boto3_resource("ec2")
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


def _security_group(manifest: Manifest, vpc_id: str) -> None:
    client = manifest.boto3_client("ec2")
    sec_groups: List[str] = [
        s["GroupId"]
        for s in client.describe_security_groups()["SecurityGroups"]
        if s["VpcId"] == vpc_id and s["GroupName"] != "default"
    ]
    if sec_groups:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(sec_groups)) as executor:
            list(executor.map(delete_sec_group, repeat(manifest), sec_groups))


def _cleanup_remaining_dependencies(manifest: Manifest) -> None:
    if manifest.vpc.vpc_id is None:
        manifest.fetch_ssm()
    if manifest.vpc.vpc_id is None:
        manifest.fetch_network_data()
    if manifest.vpc.vpc_id is None:
        raise ValueError(f"manifest.vpc.vpc_id: {manifest.vpc.vpc_id}")
    vpc_id: str = manifest.vpc.vpc_id
    _network_interface(manifest=manifest, vpc_id=vpc_id)
    _security_group(manifest=manifest, vpc_id=vpc_id)


def deploy(manifest: Manifest) -> None:
    _logger.debug("Deploying %s DEMO...", manifest.demo_stack_name)
    if manifest.demo:
        cdk.deploy(
            manifest=manifest,
            stack_name=manifest.demo_stack_name,
            app_filename="demo.py",
            args=[manifest.filename],
        )
        manifest.fetch_demo_data()
        for plugin in plugins.PLUGINS_REGISTRY.values():
            if plugin.deploy_demo_hook is not None:
                plugin.deploy_demo_hook(manifest)


def destroy(manifest: Manifest) -> None:
    for plugin in plugins.PLUGINS_REGISTRY.values():
        if plugin.destroy_demo_hook is not None:
            plugin.destroy_demo_hook(manifest)
    if manifest.demo and cfn.does_stack_exist(manifest=manifest, stack_name=manifest.demo_stack_name):
        waited: bool = False
        while cfn.does_stack_exist(manifest=manifest, stack_name=manifest.eks_stack_name):
            waited = True
            time.sleep(2)
        else:
            _logger.debug("EKSCTL stack already is cleaned")
        if waited:
            _logger.debug("Waiting EKSCTL stack clean up...")
            time.sleep(60)  # Given extra 60 seconds if the EKS stack was just delete
        _cleanup_remaining_dependencies(manifest=manifest)
        cdk.destroy(
            manifest=manifest,
            stack_name=manifest.demo_stack_name,
            app_filename="demo.py",
            args=[manifest.filename],
        )
