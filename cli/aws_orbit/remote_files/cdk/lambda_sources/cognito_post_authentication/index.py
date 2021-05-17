import json
import logging
import os
from typing import Any, Dict, Optional, cast

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
    cognito_client = boto3.client("cognito-idp")
    lambda_client = boto3.client("lambda")

    user_name = cast(str, event.get("userName"))
    user_email = cast(str, event["request"]["userAttributes"].get("email", "user@email.com"))
    user_pool_id = cast(str, event.get("userPoolId"))

    user_groups_info = cognito_client.admin_list_groups_for_user(Username=user_name, UserPoolId=user_pool_id)
    user_groups = [group.get("GroupName") for group in user_groups_info.get("Groups")]

    logger.info("Authenticated successfully:")
    logger.info(f"userName: {user_name}, userPoolId: {user_pool_id}, userGroups: {user_groups}")

    expected_user_namespaces = {user_group: user_name + "-" + user_group for user_group in user_groups}

    orbit_env = os.environ.get("ORBIT_ENV")

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
