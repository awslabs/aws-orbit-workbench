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

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
ECR_ADDRESS="${ACCOUNT_ID}".dkr.ecr."${AWS_DEFAULT_REGION}".amazonaws.com
REPOSITORY=aws-orbit-workbench/code-build-base
VERSION=$(cat ${DIR}/VERSION)

cd ${DIR}

docker build --tag ${REPOSITORY}:${VERSION} .
docker tag ${REPOSITORY}:${VERSION} ${ECR_ADDRESS}/${REPOSITORY}:${VERSION}
docker push ${ECR_ADDRESS}/${REPOSITORY}:${VERSION}


