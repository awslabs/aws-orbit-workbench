#!/usr/bin/env python
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

src_vscode_data='/opt/orbit/data/vscode/extensions/'
target_vscode_data='/home/jovyan/shared/drivers'

if ! [ -d $target_vscode_data ]; then
  mkdir -p $target_vscode_data
fi
echo "Staging vscode data on filsystem"
cp -R $src_vscode_data $target_vscode_data



