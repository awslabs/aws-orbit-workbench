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

import concurrent.futures
import logging
import random
import time
from itertools import repeat
from typing import Any, Dict, List, Optional, cast

from aws_orbit.utils import boto3_client, chunkify

_logger: logging.Logger = logging.getLogger(__name__)


def list_keys(bucket: str) -> List[Dict[str, str]]:
    client_s3 = boto3_client("s3")
    paginator = client_s3.get_paginator("list_object_versions")
    response_iterator = paginator.paginate(Bucket=bucket, PaginationConfig={"PageSize": 1000})
    keys: List[Dict[str, str]] = []
    for page in response_iterator:
        if "DeleteMarkers" in page:
            for delete_marker in page["DeleteMarkers"]:
                keys.append(
                    {
                        "Key": delete_marker["Key"],
                        "VersionId": delete_marker["VersionId"],
                    }
                )
        if "Versions" in page:
            for version in page["Versions"]:
                keys.append({"Key": version["Key"], "VersionId": version["VersionId"]})
    return keys


def _delete_objects(bucket: str, chunk: List[Dict[str, str]]) -> None:
    client_s3 = boto3_client("s3")
    try:
        client_s3.delete_objects(Bucket=bucket, Delete={"Objects": chunk})
    except client_s3.exceptions.ClientError as ex:
        if "SlowDown" in str(ex):
            time.sleep(random.randint(3, 10))
            client_s3.delete_objects(Bucket=bucket, Delete={"Objects": chunk})


def delete_objects(bucket: str, keys: Optional[List[str]] = None) -> None:
    if keys is None:
        keys_pairs: List[Dict[str, str]] = list_keys(bucket=bucket)
    else:
        keys_pairs = [{"Key": k} for k in keys]
    if keys_pairs:
        chunks: List[List[Dict[str, str]]] = chunkify(lst=keys_pairs, max_length=1_000)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            list(executor.map(_delete_objects, repeat(bucket), chunks))


def delete_bucket(bucket: str) -> None:
    client_s3 = boto3_client("s3")
    try:
        _logger.debug("Cleaning up bucket: %s", bucket)
        delete_objects(bucket=bucket)
        _logger.debug("Deleting bucket: %s", bucket)
        client_s3.delete_bucket(Bucket=bucket)
    except Exception as ex:
        if "NoSuchBucket" in str(ex):
            _logger.debug(f"Bucket ({bucket}) does not exist, skipping")
            return
        else:
            raise ex


def upload_file(src: str, bucket: str, key: str) -> None:
    client_s3 = boto3_client("s3")
    client_s3.upload_file(Filename=src, Bucket=bucket, Key=key)


def list_s3_objects(bucket: str, key: str) -> Dict[str, Any]:
    client_s3 = boto3_client("s3")
    response = client_s3.list_objects_v2(Bucket=bucket, Prefix=key)
    return cast(Dict[str, Any], response)


def delete_bucket_by_prefix(prefix: str) -> None:
    client_s3 = boto3_client("s3")
    for bucket in client_s3.list_buckets()["Buckets"]:
        if bucket["Name"].startswith(prefix):
            delete_bucket(bucket=bucket["Name"])
