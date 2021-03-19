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

#!/usr/bin/env bash
set -ex

if [[ -z "$AWS_ORBIT_ENV" ]]; then
    echo "Must provide AWS_ORBIT_ENV in environment" 1>&2
    exit 1
fi

LOCAL_NAME=jupyter-user
AWS_REPO_NAME=orbit-$AWS_ORBIT_ENV-jupyter-user

REGION=$(aws configure get region)
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
ECR_ADDRESS="${ACCOUNT_ID}".dkr.ecr."${REGION}".amazonaws.com
REPO_ADDRESS="${ECR_ADDRESS}"/"${AWS_REPO_NAME}"

aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_ADDRESS}"
docker pull "${REPO_ADDRESS}"
docker tag "${REPO_ADDRESS}" "${LOCAL_NAME}"