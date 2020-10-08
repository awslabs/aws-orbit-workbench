#!/usr/bin/env bash
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

set -ex

ENV_NAME=$1
REGION=$2

LOCAL_NAME=datamaker-jupyter-hub
ECR_NAME=datamaker-$ENV_NAME-jupyter-hub
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)

aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ACCOUNT_ID}".dkr.ecr."${REGION}".amazonaws.com || true

docker tag "${LOCAL_NAME}":latest "${ACCOUNT_ID}".dkr.ecr."${REGION}".amazonaws.com/"${ECR_NAME}":latest
docker push "${ACCOUNT_ID}".dkr.ecr."${REGION}".amazonaws.com/"${ECR_NAME}":latest
