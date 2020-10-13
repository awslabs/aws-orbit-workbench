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
from typing import Any, Dict, List, cast

import boto3
import botocore.exceptions

from datamaker_cli.commands.deploy import refresh_manifest_file_with_demo_attrs
from datamaker_cli.exceptions import VpcNotFound
from datamaker_cli.manifest import Manifest
from datamaker_cli.remote_files.cdk import demo
from datamaker_cli.services.cfn import deploy_template, destroy_stack
from datamaker_cli.utils import does_cfn_exist

STACK_NAME = "datamaker-{env_name}-demo"

_logger: logging.Logger = logging.getLogger(__name__)


def _network_interface(vpc_id: str) -> None:
    client = boto3.client("ec2")
    ec2 = boto3.resource("ec2")
    for i in client.describe_network_interfaces(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["NetworkInterfaces"]:
        try:
            network_interface = ec2.NetworkInterface(i["NetworkInterfaceId"])
            if "Interface for NAT Gateway" not in network_interface.description:
                if network_interface.attachment is not None and network_interface.attachment["Status"] == "attached":
                    network_interface.detach()
                    network_interface.reload()
                    while network_interface.attachment is None or network_interface.attachment["Status"] != "detached":
                        time.sleep(1)
                        network_interface.reload()
                    network_interface.delete()
        except botocore.exceptions.ClientError as ex:
            error: Dict[str, Any] = ex.response["Error"]
            if "is currently in use" not in error["Message"]:
                _logger.warning(f"Ignoring NetWorkInterface {i['NetworkInterfaceId']} because it stills in use.")
            if "does not exist" not in error["Message"]:
                _logger.warning(
                    f"Ignoring NetWorkInterface {i['NetworkInterfaceId']} because it does not exist anymore."
                )
            raise


def delete_sec_group(sec_group: str) -> None:
    ec2 = boto3.resource("ec2")
    try:
        sgroup = ec2.SecurityGroup(sec_group)
        if sgroup.ip_permissions:
            sgroup.revoke_ingress(IpPermissions=sgroup.ip_permissions)
        sgroup.delete()
    except botocore.exceptions.ClientError as ex:
        error: Dict[str, Any] = ex.response["Error"]
        if f"The security group '{sec_group}' does not exist" not in error["Message"]:
            raise


def _security_group(vpc_id: str) -> None:
    client = boto3.client("ec2")
    sec_groups: List[str] = [
        s["GroupId"]
        for s in client.describe_security_groups()["SecurityGroups"]
        if s["VpcId"] == vpc_id and s["GroupName"] != "default"
    ]
    if sec_groups:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(sec_groups)) as executor:
            list(executor.map(delete_sec_group, sec_groups))


def _cleanup_remaining_dependencies(manifest: Manifest) -> None:
    if manifest.vpc.vpc_id is None:
        try:
            manifest.read_ssm()
        except VpcNotFound:
            return
        vpc_id: str = cast(str, manifest.vpc.vpc_id)
    else:
        vpc_id = manifest.vpc.vpc_id
    _network_interface(vpc_id=vpc_id)
    _security_group(vpc_id=vpc_id)


def deploy(manifest: Manifest, filename: str) -> None:
    stack_name = STACK_NAME.format(env_name=manifest.name)
    _logger.debug("Stack name: %s", stack_name)
    if manifest.demo and (not does_cfn_exist(stack_name=stack_name) or manifest.dev):
        template_filename: str = demo.synth(stack_name=stack_name, filename=filename, env_name=manifest.name)
        _logger.debug("template_filename: %s", template_filename)
        deploy_template(stack_name=stack_name, filename=template_filename, env_tag=manifest.name)
        refresh_manifest_file_with_demo_attrs(filename=filename, manifest=manifest)


def destroy(manifest: Manifest) -> None:
    stack_name = STACK_NAME.format(env_name=manifest.name)
    _logger.debug("Stack name: %s", stack_name)
    if manifest.demo and does_cfn_exist(stack_name=stack_name):
        _cleanup_remaining_dependencies(manifest=manifest)
        destroy_stack(stack_name=stack_name)
