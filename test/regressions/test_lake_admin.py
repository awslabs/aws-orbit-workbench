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
from custom_resources import OrbitJobCustomApiObject
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

MANIFESTS_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "manifests",
)

#@pytest.fixture(autouse=True, scope='session', name='orbit_workspace')
# @pytest.fixture(name='orbit_workspace')
# def sess_scope():
#     """A session scope fixture."""
#     # Required os env
#     # export AWS_ORBIT_ENV=iter
#     # export AWS_ORBIT_TEAM_SPACE=lake-admin
#     workspace = get_workspace()
#     print(f"\nInside fixture workspace={workspace}\n")
#     return workspace


@pytest.mark.namespace(create=False)
@pytest.mark.testlakeadmin
def test_lakeadmin_1_ebs(kube: TestClient) -> None:
    body = {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {
            "generateName": "test-orbit-job-lake-admin-ebs-"
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
                "notebookName": "1-EBS.ipynb",
                "sourcePath": "shared/samples/notebooks/M-Admin",
                "targetPath": "shared/regression/notebooks/M-Admin",
                "params": {}
            }]
        }
    }

    print(body)
    lakeadmin = OrbitJobCustomApiObject(body)
    lakeadmin.create(namespace="lake-admin")
    # Logic to wait till OrbitJob creates
    lakeadmin.wait_until_ready(timeout=60)
    # Logic to pass or fail the pytest
    lakeadmin.wait_until_job_completes(timeout=1200)
    current_status = lakeadmin.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    #Cleanup
    lakeadmin.delete()
    assert current_status == "Complete"


@pytest.mark.namespace(create=False)
@pytest.mark.testlakeadmin
def test_lakeadmin_2_image_with_apps(kube: TestClient) -> None:
    body = {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {
            "generateName": "test-orbit-job-lake-admin-image-with-apps-"
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
                "notebookName": "2-Image_with_apps.ipynb",
                "sourcePath": "shared/samples/notebooks/M-Admin",
                "targetPath": "shared/regression/notebooks/M-Admin",
                "params": {}
            }]
        }
    }

    print(body)
    lakeadmin = OrbitJobCustomApiObject(body)
    lakeadmin.create(namespace="lake-admin")
    # Logic to wait till OrbitJob creates
    lakeadmin.wait_until_ready(timeout=60)
    # Logic to pass or fail the pytest
    lakeadmin.wait_until_job_completes(timeout=1200)
    current_status = lakeadmin.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    #Cleanup
    lakeadmin.delete()
    assert current_status == "Complete"

@pytest.mark.namespace(create=False)
@pytest.mark.testlakeadmin_lf
def test_lakeadmin_3_lf_account_settings(kube: TestClient) -> None:
    body = {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {
            "generateName": "test-orbit-job-lake-admin-lf-account-settings-"
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
                "notebookName": "4-LakeFormation-Account-Settings.ipynb",
                "sourcePath": "shared/samples/notebooks/M-Admin",
                "targetPath": "shared/regression/notebooks/M-Admin",
                "params": {}
            }]
        }
    }

    print(body)
    lakeadmin = OrbitJobCustomApiObject(body)
    lakeadmin.create(namespace="lake-admin")
    # Logic to wait till OrbitJob creates
    lakeadmin.wait_until_ready(timeout=60)
    # Logic to pass or fail the pytest
    lakeadmin.wait_until_job_completes(timeout=1200)
    current_status = lakeadmin.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    #Cleanup
    lakeadmin.delete()
    assert current_status == "Complete"