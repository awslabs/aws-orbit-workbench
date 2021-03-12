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
from typing import Dict, Tuple, TypeVar

import botocore

from aws_orbit.models.context import Context, FoundationContext
from aws_orbit.services import s3
from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


T = TypeVar("T")


def get_credential(context: T) -> Tuple[str, str]:
    if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
        raise ValueError("Unknown 'context' Type")
    if context.toolkit.s3_bucket is None:
        raise ValueError("context.toolkit.s3_bucket is None!")
    client_s3 = boto3_client(service_name="s3")
    _logger.debug(f"TOOLKIT BUCKET: {context.toolkit.s3_bucket}")
    try:
        obj = client_s3.get_object(Bucket=context.toolkit.s3_bucket, Key="cli/dockerhub.json")
        obj_json: Dict[str, str] = json.loads(obj["Body"].read())
        return obj_json["username"], obj_json["password"]
    except botocore.exceptions.ClientError as ex:
        if ex.response["ResponseMetadata"]["HTTPStatusCode"] == 404:
            return "", ""
        raise ex


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
