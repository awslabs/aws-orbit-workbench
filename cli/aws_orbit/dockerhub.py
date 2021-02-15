import json
import logging
from typing import TYPE_CHECKING, Dict, Tuple

import botocore

from aws_orbit.services import s3
from aws_orbit.utils import boto3_client

if TYPE_CHECKING:
    from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)


def get_credential(context: "Context") -> Tuple[str, str]:
    if context.toolkit.s3_bucket is None:
        raise ValueError("context.toolkit.s3_bucket is None!")
    client_s3 = boto3_client(service_name="s3")
    _logger.debug(f"TOOLKIT BUCKET: {context.toolkit.s3_bucket}")
    obj = client_s3.get_object(Bucket=context.toolkit.s3_bucket, Key="cli/dockerhub.json")
    obj_json: Dict[str, str] = json.loads(obj["Body"].read())
    return obj_json["username"], obj_json["password"]


def store_credential(context: "Context", username: str, password: str) -> None:
    if context.toolkit.s3_bucket is None:
        raise ValueError(f"context.toolkit.s3_bucket: {context.toolkit.s3_bucket}")
    s3.delete_objects(
        bucket=context.toolkit.s3_bucket,
        keys=["cli/dockerhub.json"],
    )
    _logger.debug("context.toolkit.s3_bucket: %s", context.toolkit.s3_bucket)
    client_s3 = boto3_client(service_name="s3")
    client_s3.put_object(
        Body=json.dumps({"username": username, "password": password}).encode("utf-8"),
        Bucket=context.toolkit.s3_bucket,
        Key="cli/dockerhub.json",
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=context.toolkit.kms_arn,
    )


def does_credential_exist(context: "Context") -> bool:
    if context.toolkit.s3_bucket is None:
        raise ValueError("context.toolkit.s3_bucket is None!")
    client_s3 = boto3_client(service_name="s3")
    try:
        client_s3.head_object(Bucket=context.toolkit.s3_bucket, Key="cli/dockerhub.json")
        return True
    except botocore.exceptions.ClientError as ex:
        if ex.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
            return False
        raise ex
