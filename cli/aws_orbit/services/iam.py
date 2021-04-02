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

from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def get_role(role_name: str) -> Optional[Dict[str, Any]]:
    _logger.debug(f"Getting Role: {role_name}")

    iam_client = boto3_client("iam")
    try:
        return cast(Dict[str, Any], iam_client.get_role(RoleName=role_name))
    except iam_client.exceptions.NoSuchEntityException:
        return None


def get_open_id_connect_provider(account_id: str, open_id_connect_provider_id: str) -> Optional[Dict[str, Any]]:
    open_id_connect_provider_arn = f"arn:aws:iam::{account_id}:oidc-provider/{open_id_connect_provider_id}"
    _logger.debug(f"Getting OpenIDConnectProvider: {open_id_connect_provider_arn}")

    iam_client = boto3_client("iam")
    try:
        return cast(
            Dict[str, Any],
            iam_client.get_open_id_connect_provider(OpenIDConnectProviderArn=open_id_connect_provider_arn),
        )
    except iam_client.exceptions.NoSuchEntityException:
        return None


def update_assume_role_roles(
    account_id: str,
    role_name: str,
    roles_to_add: Optional[List[str]] = None,
    roles_to_remove: Optional[List[str]] = None,
) -> None:
    if not roles_to_add and not roles_to_remove:
        raise Exception("One of roles_to_add or roles_to_remove is required")

    _logger.debug(f"Updating AssumeRolePolicy for {role_name}, Adding: {roles_to_add}, Removing: {roles_to_remove}")

    iam_client = boto3_client("iam")
    assume_role_policy = iam_client.get_role(RoleName=role_name)["Role"]["AssumeRolePolicyDocument"]

    statements = []
    roles_to_add_set = (
        set()
        if roles_to_add is None
        else {f"arn:aws:iam::{account_id}:role/{role}" for role in roles_to_add if get_role(role)}
    )
    roles_to_remove_set = (
        set() if roles_to_remove is None else {f"arn:aws:iam::{account_id}:role/{role}" for role in roles_to_remove}
    )

    _logger.debug("current_policies: %s", assume_role_policy["Statement"])
    for statement in assume_role_policy["Statement"]:
        arn = statement.get("Principal", {}).get("AWS", None)
        if arn in roles_to_remove_set:
            _logger.debug("Removing %s from AssumeRolePolicy", arn)
            continue
        elif arn in roles_to_add_set:
            _logger.debug("AssumeRolePolicy Statement (%s) found containing %s", statement, arn)
            roles_to_add_set.remove(arn)
            statements.append(statement)
        else:
            _logger.debug("Keeping %s in AssumeRolePolicy", statement)
            statements.append(statement)

    for arn in roles_to_add_set:
        _logger.debug("Adding %s to AssumeRolePolicy", arn)
        statements.append({"Effect": "Allow", "Action": "sts:AssumeRole", "Principal": {"AWS": arn}})

    assume_role_policy["Statement"] = statements
    policy_body = json.dumps(assume_role_policy)
    _logger.debug("policy_body: %s", policy_body)
    iam_client.update_assume_role_policy(RoleName=role_name, PolicyDocument=policy_body)


def add_assume_role_statement(role_name: str, statement: Dict[str, Any]) -> None:
    _logger.debug(f"Adding AssumeRolePolicy for {role_name}, Adding: {statement}")

    iam_client = boto3_client("iam")
    assume_role_policy = iam_client.get_role(RoleName=role_name)["Role"]["AssumeRolePolicyDocument"]
    statements = assume_role_policy["Statement"]

    if statement in statements:
        _logger.debug("Skipping Statement already contained by the AssumeRolePolicy")
    else:
        statements.append(statement)
        assume_role_policy["Statement"] = statements
        policy_body = json.dumps(assume_role_policy)
        _logger.debug("policy_body: %s", policy_body)
        iam_client.update_assume_role_policy(RoleName=role_name, PolicyDocument=policy_body)
