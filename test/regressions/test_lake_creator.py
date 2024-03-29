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

import os
from typing import Any, Dict
import pytest
from custom_resources import OrbitJobCustomApiObject
from kubetest.client import TestClient
from pathlib import Path

from common_utils import *
import logging
# Initialize parameters
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger()


def get_lake_creator_config() -> Dict[str, Any]:
    notebook_bucket = workspace['ScratchBucket']
    env_name = workspace['env_name']
    # Locate Bucket Paths
    demo_config = get_demo_configuration(env_name)
    lake_bucket = demo_config.get("LakeBucket").split(':::')[1]
    users_bucket = notebook_bucket.split("/")[2]
    logger.info(f"lake_bucket={lake_bucket}")
    logger.info(f"users_bucket={users_bucket}")

    # Get orbit job parameters
    database_name = f"cms_raw_db_{env_name}".replace('-', '_')  # athena doesnt support '-' in db or table name
    location = GLUE.get_database(Name=database_name)['Database']['LocationUri']
    bucket = location[5:].split('/')[0]
    logger.info(f"bucket={bucket}")
    logger.info(f"location={location}")

    sourcePrefix = "cms/"
    sourceFolder = "landing/data/" + sourcePrefix
    bucketName = bucket
    extractedPrefix = "extracted/"
    extractedFolder = f"s3://{bucketName}/{extractedPrefix}"

    return {
        "database_name": database_name,
        "bucketName": bucketName,
        "sourceFolder": sourceFolder,
        "extractedFolder": extractedFolder,
        "extractedPrefix": extractedPrefix
    }

lake_creator_config = get_lake_creator_config()

lakecreator_zip_files= get_s3_extracted_files(lake_creator_config.get("bucketName"), lake_creator_config.get("sourceFolder"))


@pytest.mark.order(1)
@pytest.mark.namespace(create=False)
@pytest.mark.testlakecreator_unzip
@pytest.mark.parametrize('zip_file', lakecreator_zip_files)
def test_lakecreator_extractor(zip_file, kube: TestClient):
    # Extract Zip Files in Parallel
    bucketName = lake_creator_config.get("bucketName")
    extractedFolder = lake_creator_config.get("extractedFolder")
    schemas = get_schemas(bucketName, 'landing/cms/schema/')

    # for key in s3.list_objects_v2(Bucket=bucketName, Prefix=sourceFolder)['Contents']:
    file = zip_file['Key']
    schema = get_schema(schemas, file)
    s3_data_folder = os.path.join(extractedFolder, schema[0] if schema[0] else "")

    notebook_to_run = {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {
            "generateName": f"test-orbit-job-lake-creator-"
        },
        "spec": {
            "taskType": "jupyter",
            "compute": {
                "nodeType": "ec2",
                "container": {
                    "concurrentProcesses": 1
                },
                "podSetting": "orbit-runner-support-small"
            },
            "tasks": [{
                "notebookName": "Example-2-Extract-Files.ipynb",
                "sourcePath": "/home/jovyan/shared/samples/notebooks/A-LakeCreator",
                "targetPath": "/home/jovyan/shared/regression/notebooks/A-LakeCreator",
                "params": {
                    "bucketName": bucketName,
                    "zipFileName": file,
                    "targetFolder": s3_data_folder,
                    "use_subdirs": "False" if schema[0] else "True"
                }
            }]
        }
    }

    logger.info(notebook_to_run)
    lakecreator = OrbitJobCustomApiObject(notebook_to_run)
    lakecreator.create(namespace="lake-creator")
    # Logic to wait till OrbitJob creates
    lakecreator.wait_until_ready(timeout=60)
    # Logic to pass or fail the pytest
    lakecreator.wait_until_job_completes(timeout=600)
    current_status = lakecreator.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    # Cleanup
    lakecreator.delete()
    assert current_status == JOB_COMPLETION_STATUS


def lake_creator_list_of_extracted_files():
    bucketName = lake_creator_config.get("bucketName")
    extractedPrefix = lake_creator_config.get("extractedPrefix")
    # returning a list
    extracted_files = []
    logger.info(f"Extracted files path s3://{bucketName}/{extractedPrefix}")
    response = S3.list_objects_v2(Bucket=bucketName, Prefix=extractedPrefix)
    if "Contents" in response:
        for object in response["Contents"]:
            logger.info(f"object={object}")
            extracted_files.append(object["Key"])
    logger.info(f"extracted_files={extracted_files}")
    return extracted_files

extracted_data_files = lake_creator_list_of_extracted_files()


@pytest.mark.order(2)
@pytest.mark.namespace(create=False)
@pytest.mark.testlakecreator_check_data_files
def test_lakecreator_s3_extracted_file_check(kube: TestClient):
    import pprint
    pprint.pprint(extracted_data_files)
    print(len(extracted_data_files))
    assert len(extracted_data_files) > 0


@pytest.mark.order(3)
@pytest.mark.namespace(create=False)
@pytest.mark.testlakecreator_create_glue_tables
@pytest.mark.parametrize('datafile', extracted_data_files)
def test_lakecreator_glue_table_creator(datafile, kube: TestClient):
    region = workspace.get("region")
    bucket_name = lake_creator_config.get("bucketName")
    database_name = lake_creator_config.get("database_name")
    schemas = get_schemas(bucket_name, 'landing/cms/schema/')

    #file = datafile
    p = Path(datafile).parent
    print(f"Path={str(p)}")
    schema = get_schema(schemas, datafile)
    from datetime import datetime
    datetimestring = datetime.now().strftime("%m%d%Y%H%M%S%f")

    notebook_to_run = {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {
            "generateName": f"test-orbit-job-lake-creator-"
        },
        "spec": {
            "taskType": "jupyter",
            "compute": {
                "nodeType": "ec2",
                "container": {
                    "concurrentProcesses": 1
                },
                "podSetting": "orbit-runner-support-small",
                "env": [{
                    'name': 'AWS_ORBIT_S3_BUCKET',
                    'value': bucket_name
                }]
            },
            "tasks": [{
                "notebookName": "Example-3-Load-Database-Athena.ipynb",
                "sourcePath": "/home/jovyan/shared/samples/notebooks/A-LakeCreator",
                "targetPath": "/home/jovyan/shared/regression/notebooks/A-LakeCreator",
                "targetPrefix": f"unsecured-{datetimestring}",
                "params": {
                    "source_bucket_name": bucket_name,
                    "target_bucket_name": bucket_name,
                    "database_name": database_name,
                    "schema_dir": "landing/cms/schema",
                    "file_path": str(p),
                    "region": region
                }
            }]
        }
    }

    print(notebook_to_run)

    lakecreator = OrbitJobCustomApiObject(notebook_to_run)
    lakecreator.create(namespace="lake-creator")
    # Logic to wait till OrbitJob creates
    lakecreator.wait_until_ready(timeout=60)
    # Logic to pass or fail the pytest
    lakecreator.wait_until_job_completes(timeout=1200)
    current_status = lakecreator.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    # Cleanup
    lakecreator.delete()
    assert current_status == JOB_COMPLETION_STATUS


#Check that Glue Tables are Created
@pytest.mark.order(4)
@pytest.mark.namespace(create=False)
@pytest.mark.testlakecreator_check_glue_tables
def test_lakecreator_glue_tables(kube: TestClient):
    database_name = lake_creator_config.get("database_name")
    res = GLUE.get_tables(DatabaseName=database_name)
    tables = res['TableList']
    raw_count = 0
    parq_count = 0
    for t in tables:
        if t['Name'].endswith('_raw'):
            raw_count += 1
        else:
            parq_count += 1
        logger.info(t['Name'])
    print(f"Total tables: {str(len(tables))}. Raw tables: {raw_count}. Final tables: {parq_count}")
    assert raw_count == parq_count and raw_count > 0


@pytest.mark.order(5)
@pytest.mark.namespace(create=False)
@pytest.mark.testlakecreator_lf
@pytest.mark.skipif("iso" in workspace.get("env_name"), reason="lakeformation endpoint is unreachable in iso env")
def test_lakecreator_lf(kube: TestClient):
    notebook_to_run = {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {
            "generateName": f"test-orbit-job-lake-creator-"
        },
        "spec": {
            "taskType": "jupyter",
            "compute": {
                "nodeType": "ec2",
                "container": {
                    "concurrentProcesses": 1
                },
                "podSetting": "orbit-runner-support-large",
            },
            "tasks": [{
                "notebookName": "Example-4-LakeFormation-Secured-DB.ipynb",
                "sourcePath": "/home/jovyan/shared/samples/notebooks/A-LakeCreator",
                "targetPath": "/home/jovyan/shared/regression/notebooks/A-LakeCreator",
            }]
        }
    }

    logger.info(f"notebook_to_run={notebook_to_run}")

    lakecreator = OrbitJobCustomApiObject(notebook_to_run)
    lakecreator.create(namespace="lake-creator")
    # Logic to wait till OrbitJob creates
    lakecreator.wait_until_ready(timeout=60)
    # Logic to pass or fail the pytest
    lakecreator.wait_until_job_completes(timeout=1800)
    current_status = lakecreator.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    # Cleanup
    lakecreator.delete()
    assert current_status == JOB_COMPLETION_STATUS
