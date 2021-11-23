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


import pytest
from custom_resources import OrbitJobCustomApiObject
from common_utils import JOB_COMPLETION_STATUS
from kubetest.client import TestClient
from aws_orbit_sdk.common import get_workspace
import logging

# Initialize parameters
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger()

workspace = get_workspace()

LAKE_ADMIN_JOB = {
    "apiVersion": "orbit.aws/v1",
    "kind": "OrbitJob",
    "metadata": {
        "generateName": "test-orbit-job-lake-admin-"
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
        "tasks": []
    }
}

@pytest.mark.namespace(create=False)
@pytest.mark.testlakeadmin_ebs
def test_lakeadmin_1_ebs(kube: TestClient) -> None:

    lake_admin_job_ebs = LAKE_ADMIN_JOB
    lake_admin_job_ebs["metadata"]["generateName"]= "test-orbit-job-lake-admin-ebs-"
    lake_admin_job_ebs["spec"]["tasks"]= [{
                "notebookName": "1-EBS.ipynb",
                "sourcePath": "shared/samples/notebooks/M-Admin",
                "targetPath": "shared/regression/notebooks/M-Admin",
                "params": {}
            }]
    logger.info(lake_admin_job_ebs)
    lakeadmin = OrbitJobCustomApiObject(lake_admin_job_ebs)
    lakeadmin.create(namespace="lake-admin")
    # Logic to wait till OrbitJob creates
    lakeadmin.wait_until_ready(timeout=120)
    # Logic to pass or fail the pytest
    lakeadmin.wait_until_job_completes(timeout=7200)
    current_status = lakeadmin.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    #Cleanup
    lakeadmin.delete()
    assert current_status == JOB_COMPLETION_STATUS


@pytest.mark.namespace(create=False)
#@pytest.mark.testlakeadmin_image_with_apps
def test_lakeadmin_2_image_with_apps(kube: TestClient) -> None:
    lake_admin_job_mage_with_apps = LAKE_ADMIN_JOB
    lake_admin_job_mage_with_apps["metadata"]["generateName"]= "test-orbit-job-lake-admin-image-with-apps-"
    lake_admin_job_mage_with_apps["spec"]["tasks"]= [{
                "notebookName": "2-Image_with_apps.ipynb",
                "sourcePath": "shared/samples/notebooks/M-Admin",
                "targetPath": "shared/regression/notebooks/M-Admin",
                "params": {}
            }]

    logger.info(lake_admin_job_mage_with_apps)
    lakeadmin = OrbitJobCustomApiObject(lake_admin_job_mage_with_apps)
    lakeadmin.create(namespace="lake-admin")
    # Logic to wait till OrbitJob creates
    lakeadmin.wait_until_ready(timeout=120)
    # Logic to pass or fail the pytest
    lakeadmin.wait_until_job_completes(timeout=7200, interval=30)
    current_status = lakeadmin.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    #Cleanup
    lakeadmin.delete()
    assert current_status == JOB_COMPLETION_STATUS

@pytest.mark.namespace(create=False)
@pytest.mark.testlakeadmin_lf
@pytest.mark.skipif("iso" in workspace.get("env_name"), reason="lakeformation endpoint is unreachable in iso env")
def test_lakeadmin_3_lf_account_settings(kube: TestClient) -> None:
    lake_admin_job_lf = LAKE_ADMIN_JOB
    lake_admin_job_lf["metadata"]["generateName"] = "test-orbit-job-lake-admin-lf-account-settings-"
    lake_admin_job_lf["spec"]["tasks"] = [{
                "notebookName": "4-LakeFormation-Account-Settings.ipynb",
                "sourcePath": "shared/samples/notebooks/M-Admin",
                "targetPath": "shared/regression/notebooks/M-Admin",
                "params": {}
            }]

    logger.info(lake_admin_job_lf)
    lakeadmin = OrbitJobCustomApiObject(lake_admin_job_lf)
    lakeadmin.create(namespace="lake-admin")
    # Logic to wait till OrbitJob creates
    lakeadmin.wait_until_ready(timeout=120)
    # Logic to pass or fail the pytest
    lakeadmin.wait_until_job_completes(timeout=7200)
    current_status = lakeadmin.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    #Cleanup
    lakeadmin.delete()
    assert current_status == JOB_COMPLETION_STATUS
