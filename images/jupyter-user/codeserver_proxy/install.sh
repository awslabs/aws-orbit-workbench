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
curl -fsSL https://code-server.dev/install.sh -o install.sh
chmod +x install.sh
./install.sh --method standalone --prefix /opt/orbit/apps/codeserver
rm -f install.sh
export PATH="/opt/orbit/apps/codeserver/bin:$PATH"

code-server --install-extension ms-python.python --force
code-server --install-extension ms-toolsai.jupyter --force
code-server --install-extension mtxr.sqltools --force
code-server --install-extension rogalmic.bash-debug --force
code-server --install-extension AmazonWebServices.aws-toolkit-vscode --force
code-server --install-extension ms-kubernetes-tools.vscode-kubernetes-tools --force

mv ~/.local/share/code-server/extensions /opt/orbit/apps/codeserver/
mv ~/.local/share/code-server/CachedExtensionVSIXs /opt/orbit/apps/codeserver/
rm -rf ~/.local/share/code-server

pip install .


