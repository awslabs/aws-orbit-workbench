import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, cast

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

orbit_env = os.environ.get("ORBIT_ENV")


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:

    cognito_client = boto3.client("cognito-idp")
    lambda_client = boto3.client("lambda")

    user_name = cast(str, event.get("userName"))
    user_email = cast(str, event["request"]["userAttributes"].get("email", "invalid_email"))

    validate_email(user_email)

    user_pool_id = cast(str, event.get("userPoolId"))

    user_groups_info = cognito_client.admin_list_groups_for_user(Username=user_name, UserPoolId=user_pool_id)
    # user_groups = [group.get("GroupName").split(f"{orbit_env}-")[1] for group in user_groups_info.get("Groups")]

    team_info = get_auth_group_from_ssm()

    user_groups = []
    for group in user_groups_info.get("Groups"):
        group_name = group.get("GroupName")
        if (f"{orbit_env}-") in group_name:
            group_name = group_name.split(f"{orbit_env}-")[1]
            for team_name in team_info:
                if group_name in team_info[team_name]:
                    g = team_name
                    user_groups.append(g)

    logger.info("Authenticated successfully:")
    logger.info(f"userName: {user_name}, userPoolId: {user_pool_id}, userGroups: {user_groups}")

    expected_user_namespaces = {user_group: user_group + "-" + user_name for user_group in user_groups}

    payload = {
        "user_name": user_name,
        "user_email": user_email,
        "user_pool_id": user_pool_id,
        "expected_user_namespaces": expected_user_namespaces,
    }
    lambda_client.invoke(
        FunctionName=f"orbit-{orbit_env}-post-auth-k8s-manage", InvocationType="Event", Payload=json.dumps(payload)
    )

    return event


def validate_email(email: str) -> None:
    # "It has exactly one @ sign, and at least one . in the part after the @"
    email_regex = re.compile(r"[^@]+@[^@]+\.[^@]+")

    if not email_regex.fullmatch(email):
        logger.error(f"{email} is not a valid email address")
        raise ValueError(f"{email} is not a valid email address")


def get_auth_group_from_ssm() -> Dict[str, List[str]]:
    ssm_client = boto3.client("ssm")

    team_info = {}

    team_manifest_pattern = re.compile(rf"/orbit/{orbit_env}/teams/.*/manifest")

    paginator = ssm_client.get_paginator("describe_parameters")
    page_iterator = paginator.paginate()

    for page in page_iterator:
        for path in page.get("Parameters"):
            param = path.get("Name")

            if team_manifest_pattern.fullmatch(param):
                param_value = json.loads(ssm_client.get_parameter(Name=param).get("Parameter").get("Value"))
                team = param.split("/")[-2]
                auth_group_val = param_value.get("AuthenticationGroups")
                team_info[team] = auth_group_val

    return team_info
