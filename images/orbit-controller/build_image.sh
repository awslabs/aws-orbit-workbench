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

# THIS SCRIPT IS ONLY NECESSARY WHILE WE DON'T HAVE A BETTER MECHANISM TO ADDRESS THAT (i.e. PLUGINS)

set -ex
export ECR_ADDRESS=$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/orbit-$ORBIT_ENV_NAME/aws-orbit-orbit-controller
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_ADDRESS}"

docker build --tag orbit-controller:$VERSION --tag orbit-controller:latest .
docker tag orbit-controller:$VERSION $ECR_ADDRESS:$VERSION
docker tag orbit-controller:latest $ECR_ADDRESS:latest
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/orbit-$ORBIT_ENV_NAME/orbit-controller:$VERSION
docker push $ACCOUNT.dkr.ecr.$REGION.amazonaws.com/orbit-$ORBIT_ENV_NAME/orbit-controller:latest
