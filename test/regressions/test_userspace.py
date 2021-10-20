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
import boto3
import json
import pytest
import logging
from typing import Any, Dict, List, Optional, cast
from custom_resources import CustomApiObject
from kubernetes import client
from kubetest.client import TestClient

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
ORBIT_ENV="iter"
TEAM_NAME = "lake-admin"

USER_NAME = "orbitpytest"
USER_EMAIL = F"{USER_NAME}@amazon.com"
USER_NS = "lake-admin-orbitpytest"

class UserSpace(CustomApiObject):
    group = "orbit.aws"
    api_version = "v1"
    kind = "UserSpace"

    def is_ready(self) -> bool:
        self.refresh()
        return self.obj.get("status", {}).get("installation", {}).get("installationStatus") == "Installed"


def create_user_efs_endpoint(user: str, team_name: str) -> Dict[str, Any]:
    ssm = boto3.client("ssm")
    env_context = ssm.get_parameter(Name=f"/orbit/{ORBIT_ENV}/context")
    EFS_FS_ID = json.loads(env_context.get("Parameter").get("Value")).get("SharedEfsFsId")
    efs = boto3.client("efs")
    return cast(
        Dict[str, str],
        efs.create_access_point(
            FileSystemId=EFS_FS_ID,
            PosixUser={"Uid": 1000, "Gid": 100},
            RootDirectory={
                "Path": f"/{team_name}/private/{user}",
                "CreationInfo": {"OwnerUid": 1000, "OwnerGid": 100, "Permissions": "770"},
            },
            Tags=[{"Key": "TeamSpace", "Value": team_name}, {"Key": "Env", "Value": ORBIT_ENV}],
        ),
    )


@pytest.mark.order(1)
@pytest.mark.namespace(create=True, name=USER_NS)
@pytest.mark.testuserspace_cr
def test_userspace_creation(kube: TestClient) -> None:
    logger.info(f"Creating EFS endpoint for {USER_NAME}...")
    resp = create_user_efs_endpoint(user=USER_NAME, team_name=TEAM_NAME)
    access_point_id = resp.get("AccessPointId")

    body = {
        "apiVersion": "orbit.aws/v1",
        "kind": "UserSpace",
        "metadata": {
            "name": USER_NS,
            "namespace": USER_NS,
        },
        "spec": {
            "env": ORBIT_ENV,
            "space": "user",
            "team": TEAM_NAME,
            "user": USER_NAME,
            "userEfsApId": access_point_id,
            "userEmail": USER_EMAIL
        },
    }
    # Create UserSpace custom resource
    userspace = UserSpace(body)
    userspace.create(namespace=TEAM_NAME)
    # Wait for creation
    userspace.wait_until_ready(timeout=30)
    # Check the Helm chart installation status
    # Delete the UserSpace custom resource
    userspace.delete()
