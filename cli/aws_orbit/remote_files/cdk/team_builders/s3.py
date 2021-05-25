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

import logging
from typing import Optional, cast

import aws_cdk.aws_kms as kms
import aws_cdk.aws_s3 as s3
import aws_cdk.core as core

_logger: logging.Logger = logging.getLogger(__name__)


class S3Builder:
    @staticmethod
    def build_s3_bucket(
        scope: core.Construct, id: str, name: str, scratch_retention_days: int, kms_key: kms.Key
    ) -> s3.Bucket:
        _logger.debug(f"Creating scratch bucket {name}")

        return s3.Bucket(
            scope=scope,
            id=id,
            bucket_name=name,
            access_control=s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=core.RemovalPolicy.RETAIN,
            lifecycle_rules=[s3.LifecycleRule(expiration=core.Duration.days(scratch_retention_days))],
            encryption=s3.BucketEncryption.KMS,
            encryption_key=cast(
                Optional[kms.IKey],
                kms_key,
            ),
        )
