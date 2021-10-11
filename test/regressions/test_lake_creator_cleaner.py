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
import pytest
from kubetest.client import TestClient
from aws_orbit_sdk.common import get_workspace
from common_utils import *

import logging
# Initialize parameters
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger()


@pytest.mark.order(1)
@pytest.mark.namespace(create=False)
@pytest.mark.testlakecreator_cleaner
def test_lake_creator_setup(kube: TestClient):
    workspace = get_workspace()
    notebook_bucket = workspace['ScratchBucket']
    env_name = workspace['env_name']
    # Locate Bucket Paths
    demo_config = get_demo_configuration(env_name)
    lake_bucket = demo_config.get("LakeBucket").split(':::')[1]
    users_bucket = notebook_bucket.split("/")[2]
    logger.info(f"lake_bucket={lake_bucket}, users_bucket={users_bucket}")
    # Create Databases
    database_name = f"cms_raw_db_{env_name}".replace('-', '_')  # athena doesnt support '-' in db or table name
    create_db(database_name, lake_bucket, 'lake: claims data from cms')
    assert check_database_exists(database_name) == database_name
    create_db('default', lake_bucket)
    assert check_database_exists('default') == 'default'
    create_db('users', users_bucket)
    assert check_database_exists('users') == 'users'
    # Get orbit job parameters
    location = GLUE.get_database(Name=database_name)['Database']['LocationUri']
    bucket = location[5:].split('/')[0]
    logger.info(f"bucket={bucket}, location={location}")
    extractedPrefix = "extracted/"
    # S3 Clean Up
    clean_bucket_prefix(bucket, extractedPrefix)
    assert len(get_s3_extracted_files(bucket, extractedPrefix)) == 0
    #sh.run("rm -f /home/jovyan/shared/regression/CREATOR_PASSED")
    clean_bucket_prefix(bucket, database_name)
    assert len(get_s3_extracted_files(bucket, database_name)) == 0
