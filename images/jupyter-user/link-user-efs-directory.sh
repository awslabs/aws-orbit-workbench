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

rm -rf /home/jovyan/work
rm -rf /home/jovyan/tmp

mkdir -p /efs/"$USERNAME"
mkdir -p /efs/shared/scheduled/notebooks
mkdir -p /efs/shared/scheduled/outputs
mkdir -p /home/jovyan/tmp

chown -R jovyan /efs/"$USERNAME"
chown -R jovyan /efs/shared

ln -s /efs/"$USERNAME"/ /home/jovyan/private
ln -s /efs/shared/ /home/jovyan/shared
