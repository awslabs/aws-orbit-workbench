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

import os
from typing import Any, Dict, Optional, cast

import boto3
import yaml

BOTO3_SESSION: boto3.Session = boto3.Session()
ENV_NAME: str = os.environ["ENV_NAME"]
TEAM: str = os.environ["TEAM"]
GRANT_SUDO: str = os.environ["GRANT_SUDO"]


def read_manifest_ssm() -> Dict[str, Any]:
    client = boto3.Session().client(service_name="ssm")
    yaml_str: str = client.get_parameter(Name=f"/orbit/{ENV_NAME}/manifest")["Parameter"]["Value"]
    return cast(Dict[str, Any], yaml.safe_load(yaml_str))


MANIFEST: Dict[str, Any] = read_manifest_ssm()
REGION: str = MANIFEST["region"]
ACCOUNT_ID: str = MANIFEST["account-id"]
COGNITO_USER_POOL_ID: str = MANIFEST["user-pool-id"]
TOOLKIT_S3_BUCKET: str = MANIFEST["toolkit-s3-bucket"]
TAG: str = MANIFEST["images"]["jupyter-user"]["version"]
IMAGE: Optional[str] = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/orbit-{ENV_NAME}-{TEAM}:latest"
IMAGE_SPARK: Optional[str] = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/orbit-{ENV_NAME}-{TEAM}-spark:latest"
CODEARTIFACT_DOMAIN: str = MANIFEST["codeartifact-domain"]
CODEARTIFACT_REPOSITORY: str = MANIFEST["codeartifact-repository"]
