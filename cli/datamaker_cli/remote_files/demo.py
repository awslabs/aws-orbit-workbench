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
import os
import time
from itertools import repeat
from typing import Any, Dict, List

import botocore.exceptions

from datamaker_cli import plugins, sh
from datamaker_cli.manifest import Manifest
from datamaker_cli.remote_files.cdk import demo
from datamaker_cli.services import cfn, s3

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


def _prepare_demo_data(manifest: Manifest) -> None:
    if manifest.toolkit_s3_bucket is None:
        manifest.fetch_ssm()
        if manifest.toolkit_s3_bucket is None:
            manifest.fetch_toolkit_data()
        else:
            raise ValueError(f"manifest.toolkit_s3_bucket: {manifest.toolkit_s3_bucket}")
    if manifest.toolkit_s3_bucket is None:
        raise ValueError(f"manifest.toolkit_s3_bucket: {manifest.toolkit_s3_bucket}")
    bucket_name: str = manifest.toolkit_s3_bucket
    bucket_key_prefix = "data/cms/"
    cms_files = [
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_Beneficiary_Summary_File_Sample_1.zip",  # noqa
        "http://downloads.cms.gov/files/DE1_0_2008_to_2010_Carrier_Claims_Sample_1A.zip",
        "http://downloads.cms.gov/files/DE1_0_2008_to_2010_Carrier_Claims_Sample_1B.zip",
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.zip",  # noqa
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.zip",  # noqa
        "http://downloads.cms.gov/files/DE1_0_2008_to_2010_Prescription_Drug_Events_Sample_1.zip",
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2009_Beneficiary_Summary_File_Sample_1.zip",  # noqa
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Statistics-Trends-and-Reports/SynPUFs/Downloads/DE1_0_2010_Beneficiary_Summary_File_Sample_20.zip",  # noqa
    ]
    cms_file_names = [fname.split("/")[-1] for fname in cms_files]
    # Find list of objects in S3 CMS path
    response = s3.list_s3_objects(manifest, bucket_name, bucket_key_prefix)
    s3_data_files = []
    if "Contents" in response.keys():
        for obj in response["Contents"]:
            file_name = obj["Key"].split("/")[-1]
            if file_name:
                s3_data_files.append(file_name)
    _logger.debug(f"data_files={s3_data_files}")
    # Check if required files are matching
    files_to_download = set(cms_file_names) - set(s3_data_files)
    if files_to_download:
        downloaded_files = []
        remote_dir = os.path.join(manifest.filename_dir, "data")
        # Download specific files and upload to S3 bucket path
        for fp in cms_files:
            file_name = fp.split("/")[-1]
            if file_name in files_to_download:
                sh.run(f"wget {fp} -P {remote_dir} -q")
                downloaded_files.append(fp)
                # Uploading to S3 data files path
                remote_src_file = os.path.join(remote_dir, file_name)
                s3_key_prefix = f"{bucket_key_prefix}{file_name}"
                _logger.debug(f"remote_src_file={remote_src_file}")
                s3.upload_file(manifest, remote_src_file, bucket_name, s3_key_prefix)
        _logger.info(f"Downloaded CSM data from {downloaded_files}")
    else:
        # Verify the S3 path
        _logger.info("Data files are up to date. No need to download")
        response = s3.list_s3_objects(manifest, bucket_name, bucket_key_prefix)
        if "Contents" in response.keys():
            for obj in response["Contents"]:
                _logger.debug(obj["Key"])


def deploy(manifest: Manifest) -> None:
    _logger.debug("Deploying %s DEMO...", manifest.demo_stack_name)
    if manifest.demo:
        template_filename: str = demo.synth(manifest=manifest)
        _logger.debug("template_filename: %s", template_filename)
        cfn.deploy_template(
            manifest=manifest,
            stack_name=manifest.demo_stack_name,
            filename=template_filename,
            env_tag=manifest.name,
        )
        manifest.fetch_demo_data()
        for plugin in plugins.PLUGINS_REGISTRY.values():
            if plugin.deploy_demo_hook is not None:
                plugin.deploy_demo_hook(manifest)
        # Adding demo data
        _prepare_demo_data(manifest)


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
        cfn.destroy_stack(manifest=manifest, stack_name=manifest.demo_stack_name)
