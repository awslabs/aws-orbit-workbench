import logging

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
    cognito_client = boto3.client("cognito-idp")

    userName = event.get("userName")
    userPoolId = event.get("userPoolId")

    userGroupsInfo = cognito_client.admin_list_groups_for_user(Username=userName, UserPoolId=userPoolId)
    userGroups = [group.get("GroupName") for group in userGroupsInfo.get("Groups")]

    logger.info("Authenticated successful")
    logger.info(userName, userPoolId, userGroups)

    return event
