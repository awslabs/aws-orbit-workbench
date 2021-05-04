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

REPOSITORY="public.ecr.aws/v3o4w1g6/aws-orbit-workbench/k8s-webhook-cert-manager"
VERSION=$(cat${DIR}/VERSION)

aws ecr-public get-login-password | docker login --username AWS --password-stdin public.ecr.aws/v3o4w1g6
cd ${DIR}/k8s-webhook-cert-manager

docker build --tag ${REPOSITORY}:${VERSION} .
docker push ${REPOSITORY}:${VERSION}

docker tag ${REPOSITORY}:${VERSION} ${REPOSITORY}:latest
docker push ${REPOSITORY}:latest
