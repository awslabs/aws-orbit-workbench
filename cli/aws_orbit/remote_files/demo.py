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
from typing import Any, Dict, List

from aws_orbit import ORBIT_CLI_ROOT, cdk, cleanup, exceptions, sh
from aws_orbit.manifest import Manifest
from aws_orbit.services import cfn, s3, vpc

_logger: logging.Logger = logging.getLogger(__name__)


def _download_demo_data(
    manifest: Manifest, bucket_name: str, bucket_key_prefix: str, download_files: List[str]
) -> None:
    # Verify existence of demo data, conditionally download the demo data and upload to toolkit bucket.
    # Prepare file names list
    download_file_names = [fname.split("/")[-1] for fname in download_files]
    # Find list of objects in S3 path
    response = s3.list_s3_objects(manifest, bucket_name, bucket_key_prefix)
    s3_data_files = []
    if "Contents" in response.keys():
        for obj in response["Contents"]:
            file_name = obj["Key"].split("/")[-1]
            if file_name:
                s3_data_files.append(file_name)
    _logger.debug(f"data_files={s3_data_files}")
    # Check if required files are matching
    files_to_download = set(download_file_names) - set(s3_data_files)
    if files_to_download:
        downloaded_files = []
        remote_dir = os.path.join(os.path.dirname(manifest.filename_dir), "data")
        # Download specific files and upload to S3 bucket path
        for fp in download_files:
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


def _prepare_demo_data(manifest: Manifest) -> None:
    # Check toolkit bucket details
    if manifest.toolkit_s3_bucket is None:
        _logger.info("manifest.toolkit_s3_bucket is none, fetching from ssm")
        manifest.fetch_ssm()
    if manifest.toolkit_s3_bucket is None:
        _logger.info("manifest.toolkit_s3_bucket is none, fetching from toolkit data")
        manifest.fetch_toolkit_data()
    if manifest.toolkit_s3_bucket is None:
        raise ValueError("manifest.toolkit_s3_bucket is not defined")
    bucket_name: str = manifest.toolkit_s3_bucket
    _logger.debug("Adding CMS data sets")
    cms_files: List[str] = [
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_Beneficiary_Summary_File_Sample_1.zip",  # noqa
        "http://downloads.cms.gov/files/DE1_0_2008_to_2010_Carrier_Claims_Sample_1A.zip",
        "http://downloads.cms.gov/files/DE1_0_2008_to_2010_Carrier_Claims_Sample_1B.zip",
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.zip",  # noqa
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.zip",  # noqa
        "http://downloads.cms.gov/files/DE1_0_2008_to_2010_Prescription_Drug_Events_Sample_1.zip",
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/Downloads/DE1_0_2009_Beneficiary_Summary_File_Sample_1.zip",  # noqa
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Statistics-Trends-and-Reports/SynPUFs/Downloads/DE1_0_2010_Beneficiary_Summary_File_Sample_20.zip",  # noqa
    ]
    _download_demo_data(
        manifest=manifest, bucket_name=bucket_name, bucket_key_prefix="data/cms/", download_files=cms_files
    )
    _logger.debug("Adding SageMaker regression notebooks data sets")
    sagemaker_files: List[str] = [
        "https://archive.ics.uci.edu/ml/machine-learning-databases/breast-cancer-wisconsin/wdbc.data",
        "https://github.com/mnielsen/neural-networks-and-deep-learning/raw/master/data/mnist.pkl.gz",
    ]
    _download_demo_data(
        manifest=manifest, bucket_name=bucket_name, bucket_key_prefix="data/sagemaker/", download_files=sagemaker_files
    )
    _logger.debug("Adding CSM schema files")
    cms_schema_files = os.path.join(ORBIT_CLI_ROOT, "data", "cms", "schema")
    schema_key_prefix = "cms/schema/"
    sh.run(f"aws s3 cp --recursive {cms_schema_files} s3://{bucket_name}/{schema_key_prefix}")


def deploy(manifest: Manifest) -> None:
    stack_name: str = manifest.demo_stack_name
    _logger.debug("Deploying %s DEMO...", stack_name)
    if manifest.demo:
        deploy_args: Dict[str, Any] = {
            "manifest": manifest,
            "stack_name": stack_name,
            "app_filename": os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "demo.py"),
            "args": [manifest.filename],
        }
        try:
            cdk.deploy(**deploy_args)
        except exceptions.FailedShellCommand:
            if cfn.get_eventual_consistency_event(manifest=manifest, stack_name=stack_name) is not None:
                destroy(manifest=manifest)
                _logger.debug("Sleeping for 5 minutes waiting for DEMO eventual consistency issue...")
                time.sleep(300)
                _logger.debug("Retrying DEMO deploy...")
                cdk.deploy(**deploy_args)
            else:
                raise
        manifest.fetch_demo_data()
        manifest.write_manifest_file()
        _logger.debug("Adding demo data")
        _prepare_demo_data(manifest)
        _logger.debug("Enabling private dns for codeartifact vpc endpoints")
        vpc.modify_vpc_endpoint(manifest=manifest, service_name="codeartifact.repositories", private_dns_enabled=True)
        vpc.modify_vpc_endpoint(manifest=manifest, service_name="codeartifact.api", private_dns_enabled=True)


def destroy(manifest: Manifest) -> None:
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
        cleanup.demo_remaining_dependencies(manifest=manifest)
        _logger.debug("Destroying DEMO...")
        if hasattr(manifest, "filename") and manifest.filename:
            cdk.destroy(
                manifest=manifest,
                stack_name=manifest.demo_stack_name,
                app_filename=os.path.join(ORBIT_CLI_ROOT, "remote_files", "cdk", "demo.py"),
                args=[manifest.filename],
            )
        else:
            cfn.destroy_stack(manifest=manifest, stack_name=manifest.demo_stack_name)
