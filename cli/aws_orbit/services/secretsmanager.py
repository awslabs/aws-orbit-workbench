import json
import logging
from typing import Dict

from aws_orbit.utils import boto3_client
from botocore.exceptions import ClientError

_logger: logging.Logger = logging.getLogger(__name__)


def get_docker_credentials(env_name: str) -> Dict[str, Dict[str, str]]:
    secret_name = f"orbit-{env_name}-docker-credentials"

    client = boto3_client("secretsmanager")

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        _logger.exception(e)
        return {}
    else:
        secret = json.loads(get_secret_value_response.get("SecretString", "{}"))
        return {k: json.loads(v) for k, v in secret.items()}


def put_docker_credentials(env_name: str, credentials: Dict[str, Dict[str, str]]) -> None:
    secret_name = f"orbit-{env_name}-docker-credentials"

    client = boto3_client("secretsmanager")

    try:
        client.put_secret_value(SecretId=secret_name, SecretString=json.dumps(credentials))
    except ClientError as e:
        _logger.exception(e)


def delete_docker_credentials(env_name: str) -> None:
    secret_name = f"orbit-{env_name}-docker-credentials"

    client = boto3_client("secretsmanager")

    try:
        client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
    except ClientError as e:
        _logger.exception(e)
