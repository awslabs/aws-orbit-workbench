import json
import logging
import os
import re
from typing import Any, Dict, Optional, cast

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
    orbit_env = os.environ.get("ORBIT_ENV")

    cognito_client = boto3.client("cognito-idp")
    lambda_client = boto3.client("lambda")

    user_name = cast(str, event.get("userName"))
    user_email = cast(str, event["request"]["userAttributes"].get("email", "invalid_email"))

    validate_email(user_email)

    user_pool_id = cast(str, event.get("userPoolId"))

    user_groups_info = cognito_client.admin_list_groups_for_user(Username=user_name, UserPoolId=user_pool_id)
    user_groups = [group.get("GroupName").split(f"{orbit_env}-")[1] for group in user_groups_info.get("Groups")]

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
