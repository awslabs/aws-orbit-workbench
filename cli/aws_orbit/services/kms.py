import base64
import logging
from typing import cast

from aws_orbit.models.context import Context
from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def encrypt(context: Context, plaintext: str) -> str:
    client = boto3_client("kms")

    _logger.debug("Encrypting data")
    response = client.encrypt(KeyId=context.toolkit.kms_arn, Plaintext=plaintext.encode("utf-8"))
    return base64.b64encode(response.get("CiphertextBlob")).decode("utf-8")


def decrypt(context: Context, ciphertext: str) -> str:
    client = boto3_client("kms")

    _logger.debug("Decrypting data")
    response = client.decrypt(KeyId=context.toolkit.kms_arn, CiphertextBlob=base64.b64decode(ciphertext))
    return cast(str, response["Plaintext"].decode("utf-8"))
