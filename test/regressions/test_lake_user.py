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
from pathlib import Path
from common_utils import JOB_COMPLETION_STATUS

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

def get_lake_creator_list_of_files():
    orbit_workspace = get_workspace()
    env_name = orbit_workspace['env_name']

    notebooks_run_config = {
        # a list of notebooks names to skip the execution for. Example: ["Example-7-Data-Profiling"]
        "exclusion_list": ['Example-3-Ray Job Example', 'Example-4-Ray Tune Example', 'Example-92-Delete-DemoCronJobs',
                       'Example-1-simple', 'Example-2-spark', 'Example-3-gpu', 'Example-90-Failure-Behavior'],
        "inclusion_list": [],  # if not empty, only those will run. Example: ["Example-7-Data-Profiling"]
        "optional_list": [],
        # indicates to ignore a failure. Example: ["Example-6-Schedule-Notebook", "Example-8-LakeFormation-Security"]
        "minimum_successful": 1,
        # number of minimum notebooks to be completed to consider entire test not failed
        # (has an effect when this number is larger than number of mandatory )
        "maxRetries": 3,  # max number of attempts to execute a notebook
        "notebooks_to_run": [],  # all noootebooks for execution.
        "sagemaker_notebooks_list": ["Example-1-xgboost_mnist",
                                     "Example-2-SageMaker-Batch Transform - breast cancer prediction with high level SDK",
                                     "Example-5-SageMaker-on-EKS-xgboost_mnist"]
        # sagemaker notebooks with small profile
    }

    # If we are running in an isolated env, here is your exclusion_list addition
    if env_name.endswith('-iso'):
        notebooks_run_config["exclusion_list"].append('Example-91-LakeFormation-Security')
        notebooks_run_config["exclusion_list"].append('Example-5-SageMaker-on-EKS-xgboost_mnist')

    sample_notebooks_path = "../../samples/notebooks"
    analyst_folders = ["B-DataAnalyst", "I-Image", "H-Model-Development"]
    notebook_file_path = []
    # List specific folders for analyst notebooks
    for folder in analyst_folders:
        logger.info(f"Reading folder={folder}")
        notebooks = [str(nb) for nb in Path(f"{sample_notebooks_path}/{folder}").glob("*.ipynb")]
        notebook_file_path += notebooks
    sorted_notebook_paths = sorted(notebook_file_path)

    for p in sorted_notebook_paths:
        parts = p.split('/')
        nb_file_name, nb_folder = parts[-1], parts[-2]
        nb_name= nb_file_name.split('.')[0]
        logger.info(f"nb_folder={nb_folder}/nb_name={nb_name}")
        if nb_name.split('.')[0] in notebooks_run_config["exclusion_list"]:
            # ignore inclusion_list. exclusion_list is having highest priority for filters
            logger.info(f"Ignoring notebook={nb_name}")
            continue
        if not notebooks_run_config["inclusion_list"] or nb_name in notebooks_run_config["inclusion_list"]:
            # run notebook if white list is empty or if the notebook is in white list.
            if nb_folder in ["H-Model-Development"]:
                notebooks_run_config["notebooks_to_run"].append(
                    {"folder": nb_folder, "name": nb_file_name, "profile": "small"})
            else:
                notebooks_run_config["notebooks_to_run"].append({"folder": nb_folder, "name": nb_file_name})

    return notebooks_run_config


lake_creator_list_of_files= get_lake_creator_list_of_files()
notebooks_to_run= lake_creator_list_of_files["notebooks_to_run"]


@pytest.mark.namespace(create=False)
@pytest.mark.testlakeuser
@pytest.mark.parametrize('notebook_to_run', [notebooks_to_run[0]])
def test_lakeuser_notebooks(notebook_to_run, kube: TestClient) -> None:
    logger.info(f"notebook_to_run={notebook_to_run}")
    notebook_file_name = notebook_to_run['name'].split(".")[0]
    podsetting_name = "orbit-runner-support-xlarge" if notebook_file_name in lake_creator_list_of_files['sagemaker_notebooks_list'] else "orbit-runner-support-large"
    body = {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {
            "generateName": "test-orbit-job-lake-user-"
        },
        "spec": {
            "taskType": "jupyter",
            "compute": {
                 "nodeType": "ec2",
                 "container": {
                     "concurrentProcesses": 1
                 },
                 "podSetting": podsetting_name
            },
            "tasks": [{
                "notebookName": notebook_to_run['name'],
                "sourcePath": f"shared/samples/notebooks/{notebook_to_run['folder']}",
                "targetPath": f"shared/regression/notebooks/{notebook_to_run['folder']}",
                "params": {}
            }]
        }
    }

    logger.info(body)
    lakeuser = OrbitJobCustomApiObject(body)
    lakeuser.create(namespace="lake-user")
    # Logic to wait till OrbitJob creates
    lakeuser.wait_until_ready(timeout=60)
    # Logic to pass or fail the pytest
    lakeuser.wait_until_job_completes(timeout=1200)
    current_status = lakeuser.get_status().get("orbitJobOperator").get("jobStatus")
    logger.info(f"current_status={current_status}")
    #Cleanup
    lakeuser.delete()
    assert current_status == JOB_COMPLETION_STATUS

