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
LOCAL_PATH="/home/jovyan/shared/samples"

mkdir -p $LOCAL_PATH
S3_PATH="s3://$AWS_ORBIT_S3_BUCKET/samples/"

rm -fR $LOCAL_PATH
mkdir -p $LOCAL_PATH
aws s3 cp --recursive $S3_PATH $LOCAL_PATH
