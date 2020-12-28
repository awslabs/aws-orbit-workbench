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

from typing import Any, Dict

import aws_cdk.aws_s3 as s3
import aws_cdk.core as core
from aws_cdk.core import Construct, Environment, Stack, Tags
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.plugins.helpers import cdk_handler


class MyStack(Stack):
    def __init__(
        self, scope: Construct, id: str, manifest: Manifest, team_manifest: TeamManifest, parameters: Dict[str, Any]
    ) -> None:

        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=manifest.account_id, region=manifest.region),
        )
        Tags.of(scope=self).add(key="Env", value=f"orbit-{manifest.name}")

        suffix: str = parameters.get("BucketNameInjection", "foo")
        bucket_name: str = (
            f"orbit-{team_manifest.manifest.name}-{team_manifest.name}"
            f"-{suffix}-scratch-{core.Aws.ACCOUNT_ID}-{manifest.deploy_id}"
        )

        s3.Bucket(
            scope=self,
            id="hello_bucket",
            bucket_name=bucket_name,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=core.RemovalPolicy.DESTROY,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )


if __name__ == "__main__":
    cdk_handler(stack_class=MyStack)
