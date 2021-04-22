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
echo `pwd`
curl -fsSL https://code-server.dev/install.sh | sh
code-server --install-extension ms-python.python --force
code-server --install-extension ms-toolsai.jupyter --force
code-server --install-extension mtxr.sqltools --force
code-server --install-extension extension-vsix/mtxr.sqltools-driver-pg-0.2.0.vsix --force
code-server --install-extension extension-vsix/natqe.reload-0.0.6.vsix --force
code-server --install-extension extension-vsix/rogalmic.bash-debug-0.3.9.vsix --force
code-server --install-extension AmazonWebServices.aws-toolkit-vscode --force
pip install .


