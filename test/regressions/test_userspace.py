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
from typing import Any, Dict, cast
from custom_resources import OrbitUserSpaceCrObject
from kubetest.client import TestClient
from kubernetes.client.rest import ApiException

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger()

AWS_ORBIT_ENV = os.environ.get("AWS_ORBIT_ENV")
AWS_ORBIT_TEAM_SPACE = os.environ.get("AWS_ORBIT_TEAM_SPACE")

USER_NAME = "orbitpytest"
USER_EMAIL = F"{USER_NAME}@amazon.com"
USER_NS = f"{AWS_ORBIT_TEAM_SPACE}-orbitpytest"


def create_user_efs_acesspoint(user: str, env_name: str, team_name: str) -> Dict[str, Any]:
    ssm = boto3.client("ssm")
    env_context = ssm.get_parameter(Name=f"/orbit/{env_name}/context")
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
            Tags=[{"Key": "TeamSpace", "Value": team_name}, {"Key": "Env", "Value": env_name}],
        ),
    )


def delete_user_efs_acesspoint(efs_access_point_id: str) -> bool:
    efs = boto3.client("efs")
    efs_del_status = True
    try:
        efs.delete_access_point(AccessPointId=efs_access_point_id)
    except Exception as e:
        efs_del_status = False
        logger.error(f"Error while deleting efs access point {e}")
    return efs_del_status


@pytest.mark.order(1)
@pytest.mark.namespace(create=True, name=USER_NS)
@pytest.mark.testlakeadmin_userspace_cr
def test_userspace_creation(kube: TestClient) -> None:
    logger.info(f"Creating EFS endpoint for {USER_NAME}...")
    resp = create_user_efs_acesspoint(user=USER_NAME, env_name=AWS_ORBIT_ENV, team_name=AWS_ORBIT_TEAM_SPACE)
    logger.info(f"EFS access point response={resp}")
    access_point_id = resp.get("AccessPointId")
    logger.info(f"access_point_id={access_point_id}")

    body = {
        "apiVersion": "orbit.aws/v1",
        "kind": "UserSpace",
        "metadata": {
            "name": USER_NS,
            "namespace": USER_NS,
        },
        "spec": {
            "env": AWS_ORBIT_ENV,
            "space": "user",
            "team": AWS_ORBIT_TEAM_SPACE,
            "user": USER_NAME,
            "userEfsApId": access_point_id,
            "userEmail": USER_EMAIL
        },
    }
    # Create UserSpace custom resource
    userspace_cr = OrbitUserSpaceCrObject(body)
    userspace_cr.create(namespace=USER_NS)
    # Wait for creation, check the Helm chart installation status
    userspace_cr.wait_until_ready(timeout=30)
    # Logic to pass or fail the pytest
    userspace_cr.wait_until_userspace_installation(timeout=120)
    current_status = userspace_cr.get_status().get("userSpaceOperator").get("installationStatus")
    logger.info(f"current_status={current_status}")
    assert current_status == "Installed"
    # Delete the UserSpace custom resource
    assert userspace_cr.check_userspace_exists() == True
    # Cleanup
    userspace_cr.delete()
    assert userspace_cr.check_userspace_exists() == False
    assert delete_user_efs_acesspoint(access_point_id)
