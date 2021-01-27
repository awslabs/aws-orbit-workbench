def get_users_url(user_pool_id: str, region: str) -> str:
    return f"https://{region}.console.aws.amazon.com/cognito/users/?region={region}#/pool/{user_pool_id}/users"


def get_pool_arn(user_pool_id: str, region: str, account: str) -> str:
    return f"arn:aws:cognito-idp:{region}:{account}:userpool/{user_pool_id}"
