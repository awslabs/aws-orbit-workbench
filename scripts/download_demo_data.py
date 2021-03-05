import sys
import logging
from typing import List
from aws_orbit.models.context import Context,ContextSerDe
import os
from aws_orbit import sh
from aws_orbit.services import s3
from aws_orbit import ORBIT_CLI_ROOT

_logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
# Helper function to download the demo data from public sites.
# Usage - python download_demo_data.py dev_env

def _download_demo_data(bucket_name: str, bucket_key_prefix: str, download_files: List[str]) -> None:
    # Verify existence of demo data, conditionally download the demo data and upload to toolkit bucket.
    # Prepare file names list
    download_file_names = [fname.split("/")[-1] for fname in download_files]
    # Find list of objects in S3 path
    response = s3.list_s3_objects(bucket_name, bucket_key_prefix)
    s3_data_files = []
    if "Contents" in response.keys():
        for obj in response["Contents"]:
            file_name = obj["Key"].split("/")[-1]
            if file_name:
                s3_data_files.append(file_name)
    _logger.info(f"data_files={s3_data_files}")
    # Check if required files are matching
    files_to_download = set(download_file_names) - set(s3_data_files)
    if files_to_download:
        downloaded_files = []
        remote_dir = os.path.join(os.getcwd(), "data")
        # Download specific files and upload to S3 bucket path
        for fp in download_files:
            file_name = fp.split("/")[-1]
            if file_name in files_to_download:
                sh.run(f"wget {fp} -P {remote_dir} -q")
                downloaded_files.append(fp)
                # Uploading to S3 data files path
                remote_src_file = os.path.join(remote_dir, file_name)
                s3_key_prefix = f"{bucket_key_prefix}{file_name}"
                _logger.info(f"uploading {remote_src_file} to s3 {bucket_name}/{s3_key_prefix")
                s3.upload_file(remote_src_file, bucket_name, s3_key_prefix)
        _logger.info(f"Downloaded CSM data from {downloaded_files}")
    else:
        # Verify the S3 path
        _logger.info("Data files are up to date. No need to download")
        response = s3.list_s3_objects(bucket_name, bucket_key_prefix)
        if "Contents" in response.keys():
            for obj in response["Contents"]:
                _logger.debug(obj["Key"])


def _prepare_demo_data(context: "Context") -> None:
    # Check toolkit bucket details
    if context.toolkit.s3_bucket is None:
        raise ValueError("manifest.toolkit_s3_bucket is not defined")
    bucket_name: str = context.toolkit.s3_bucket
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
    _download_demo_data(bucket_name=bucket_name, bucket_key_prefix="data/cms/", download_files=cms_files)
    _logger.debug("Adding SageMaker regression notebooks data sets")
    sagemaker_files: List[str] = [
        "https://archive.ics.uci.edu/ml/machine-learning-databases/breast-cancer-wisconsin/wdbc.data",
        "https://github.com/mnielsen/neural-networks-and-deep-learning/raw/master/data/mnist.pkl.gz",
    ]
    _download_demo_data(bucket_name=bucket_name, bucket_key_prefix="data/sagemaker/", download_files=sagemaker_files)
    _logger.debug("Adding CSM schema files")
    cms_schema_files = os.path.join(ORBIT_CLI_ROOT, "data", "cms", "schema")
    schema_key_prefix = "cms/schema/"
    sh.run(f"aws s3 cp --recursive {cms_schema_files} s3://{bucket_name}/{schema_key_prefix}")


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 2:
        env_name = sys.argv[1]
    else:
        raise ValueError("Orbit environment name required")
        sys.exit(1)
    try:
        _logger.info(f"Preparing context for environment {env_name}")
        context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
        _prepare_demo_data(context=context)
    except Exception as ex:
        error = ex.response["Error"]
        _logger.error("Invalid environment %s. Cause: %s", env_name, error)
        sys.exit(1)


if __name__ == "__main__":
    main()
