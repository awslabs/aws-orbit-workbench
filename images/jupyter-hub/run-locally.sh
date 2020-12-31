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

AWS_DEFAULT_REGION=$(aws configure get region)
`(isengardcli creds)`



docker run \
    -e JUPYTERHUB_PRIVATE_SERVICE_HOST=127.0.0.1 \
    -e JUPYTERHUB_PRIVATE_SERVICE_PORT=8005 \
    -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
    -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
    -e AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN} \
    -e AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION} \
    -e GRANT_SUDO=${GRANT_SUDO} \
    -e TEAM=lake-creator \
    -e ENV_NAME=dev-env \
    -p 8005:8005 \
    -p 8000:8000 \
    -p 8001:8001 \
    --rm \
    -it \
    orbit-jupyter-hub:1.0