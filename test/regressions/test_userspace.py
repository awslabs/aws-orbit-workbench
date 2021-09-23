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


class UserSpace(CustomApiObject):
    group = "orbit.aws"
    api_version = "v1"
    kind = "UserSpace"

    def is_ready(self) -> bool:
        self.refresh()
        return self.obj.get("status", {}).get("installation", {}).get("installationStatus") == "Installed"


@pytest.mark.order(1)
@pytest.mark.namespace(create=False)
def test_userspace(kube: TestClient) -> None:
    body = {
        "apiVersion": "orbit.aws/v1",
        "kind": "UserSpace",
        "metadata": {
            "name": "user-space-test",
        },
        "spec": {
            "env": "dev-env",
            "space": "user",
            "team": "test-team",
            "user": "test-user",
            "userEfsApId": "test-userEfsApId",
            "userEmail": "test-userEmail",
        },
    }

    userspace = UserSpace(body)
    userspace.create(namespace="orbit-system")
    userspace.wait_until_ready(timeout=30)
    userspace.delete()
