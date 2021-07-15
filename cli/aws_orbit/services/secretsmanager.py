import json
import logging
from typing import Any, Dict, cast

from botocore.exceptions import ClientError

from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def get_secret_value(secret_id: str) -> Dict[str, Any]:
    client = boto3_client("secretsmanager")

    try:
        _logger.debug("Getting Secret: %s", secret_id)
        get_secret_value_response = client.get_secret_value(SecretId=secret_id)
    except ClientError as e:
        _logger.exception(e)
        return {}
    else:
        return cast(Dict[str, Any], json.loads(get_secret_value_response.get("SecretString", "{}")))


def put_secret_value(secret_id: str, secret: Dict[str, Any]) -> None:
    client = boto3_client("secretsmanager")

    try:
        _logger.debug("Creating Secret: %s", secret_id)
        client.create_secret(Name=secret_id, SecretString="{}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceExistsException":
            _logger.info("Secret %s exists, ignoring", secret_id)
        else:
            _logger.exception(e)
            raise e

    try:
        _logger.debug("Putting Secret Value: %s", secret_id)
        client.put_secret_value(SecretId=secret_id, SecretString=json.dumps(secret))
    except ClientError as e:
        _logger.exception(e)


def delete_docker_credentials(secret_id: str) -> None:
    client = boto3_client("secretsmanager")

    try:
        _logger.debug("Deleting Secret: %s", secret_id)
        client.delete_secret(SecretId=secret_id, ForceDeleteWithoutRecovery=True)
    except ClientError as e:
        _logger.exception(e)
