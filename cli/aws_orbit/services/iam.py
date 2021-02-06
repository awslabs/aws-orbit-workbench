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

import json
import logging
from typing import Any, Dict, List, Optional, cast

from aws_orbit.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def get_open_id_connect_provider(manifest: Manifest, open_id_connect_provider_id: str) -> Optional[Dict[str, Any]]:
    open_id_connect_provider_arn = f"arn:aws:iam::{manifest.account_id}:oidc-provider/{open_id_connect_provider_id}"
    _logger.debug(f"Getting OpenIDConnectProvider: {open_id_connect_provider_arn}")

    iam_client = manifest.boto3_client("iam")
    try:
        return cast(
            Dict[str, Any],
            iam_client.get_open_id_connect_provider(OpenIDConnectProviderArn=open_id_connect_provider_arn),
        )
    except iam_client.exceptions.NoSuchEntityException:
        return None

def update_assume_role_roles(
    manifest: Manifest,
    role_name: str,
    roles_to_add: Optional[List[str]] = None,
    roles_to_remove: Optional[List[str]] = None,
) -> None:
    if not roles_to_add and not roles_to_remove:
        raise Exception("One of roles_to_add or roles_to_remove is required")

    _logger.debug(f"Updating AssumeRolePolicy for {role_name}, Adding: {roles_to_add}, Removing: {roles_to_remove}")

    iam_client = manifest.boto3_client("iam")
    assume_role_policy = iam_client.get_role(RoleName=role_name)["Role"]["AssumeRolePolicyDocument"]

    statements = []
    roles_to_add_set = (
        set() if roles_to_add is None else {f"arn:aws:iam::{manifest.account_id}:role/{role}" for role in roles_to_add}
    )
    roles_to_remove_set = (
        set()
        if roles_to_remove is None
        else {f"arn:aws:iam::{manifest.account_id}:role/{role}" for role in roles_to_remove}
    )

    for statement in assume_role_policy["Statement"]:
        arn = statement.get("Principal", {}).get("AWS", None)
        if arn in roles_to_remove_set:
            _logger.debug("Removing %s from AssumeRolePolicy", arn)
            continue
        elif arn in roles_to_add_set:
            _logger.debug("AssumeRolePolicy already contains %s", arn)
            roles_to_add_set.remove(arn)
        else:
            _logger.debug("Keeping %s in AssumeRolePolicy", statement)
            statements.append(statement)

    for arn in roles_to_add_set:
        _logger.debug("Adding %s to AssumeRolePolicy")
        statements.append({"Effect": "Allow", "Action": "sts:AssumeRole", "Principal": {"AWS": arn}})

    assume_role_policy["Statement"] = statements
    iam_client.update_assume_role_policy(RoleName=role_name, PolicyDocument=json.dumps(assume_role_policy))
