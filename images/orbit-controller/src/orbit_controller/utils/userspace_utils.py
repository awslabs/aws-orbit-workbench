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

from typing import Any, Dict, Optional

import kopf
from kubernetes import dynamic
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION


def construct(
    name: str,
    env: str,
    space: str,
    team: str,
    user: str,
    user_efsapid: str,
    user_email: str,
    owner_reference: Optional[Dict[str, str]] = None,
    labels: Optional[Dict[str, str]] = None,
    annnotations: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    userspace: Dict[str, Any] = {
        "apiVersion": f"{ORBIT_API_GROUP}/{ORBIT_API_VERSION}",
        "kind": "UserSpace",
        "metadata": {
            "name": name,
            "labels": labels,
            "annotations": annnotations,
        },
        "spec": {
            "env": env,
            "space": space,
            "team": team,
            "user": user,
            "userEfsApId": user_efsapid,
            "userEmail": user_email,
        },
    }
    if owner_reference is not None:
        userspace["metadata"]["ownerReferences"] = [owner_reference]
    return userspace


def create_userspace(
    namespace: str,
    userspace: Dict[str, Any],
    client: dynamic.DynamicClient,
    logger: kopf.Logger,
) -> None:
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="UserSpace")
    api.create(namespace=namespace, body=userspace)
    logger.debug(
        "Created UserSpace: %s in Namespace: %s",
        userspace["metadata"]["name"],
        namespace,
    )


def modify_userspace(
    namespace: str,
    name: str,
    desc: str,
    client: dynamic.DynamicClient,
    logger: kopf.Logger,
) -> None:
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="UserSpace")
    patch = {"spec": {"desc": desc}}
    api.patch(namespace=namespace, name=name, body=patch)
    logger.debug("Modified UserSpace: %s in Namespace: %s", name, namespace)


def delete_userspace(namespace: str, name: str, client: dynamic.DynamicClient, logger: kopf.Logger) -> None:
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="UserSpace")
    api.delete(namespace=namespace, name=name, body={})
    logger.debug("Deleted UserSpace: %s in Namesapce: %s", name, namespace)
