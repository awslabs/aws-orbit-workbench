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
from custom_resources import CustomApiObject
from kubetest.client import TestClient


MANIFESTS_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "manifests",
)


class LakeAdmin(CustomApiObject):
    group = "orbit.aws"
    api_version = "v1"
    kind = "OrbitJob"

    def is_ready(self) -> bool:
        self.refresh()
        return self.obj.get("status", {}).get("orbitJobOperator", {}).get("jobStatus") == "JobCreated"


@pytest.mark.order(1)
@pytest.mark.namespace(create=False)
@pytest.mark.testlakeadmin
def test_lakeadmin(kube: TestClient) -> None:
    body = {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {
            "name": "test-orbit-job"
        },
        "spec": {
            "taskType": "jupyter",
            "compute": {
                 "nodeType": "ec2",
                 "container": {
                     "concurrentProcesses": 1
                 },
                 "podSetting": "orbit-runner-support-large"
            },
            "tasks": [{
                "notebookName": "Example-1-SQL-Analysis-Athena.ipynb",
                "sourcePath": "shared/samples/notebooks/B-DataAnalyst",
                "targetPath": "shared/regression/notebooks/B-DataAnalyst",
                "targetPrefix": "yyy",
                "params": {
                    "glue_db": "glue_database",
                    "target_db": "users"
                }
            }]
        }
    }

    print(body)
    lakeadmin = LakeAdmin(body)
    lakeadmin.create(namespace="lake-admin")
    lakeadmin.wait_until_ready(timeout=30)
    #lakeadmin.delete()
