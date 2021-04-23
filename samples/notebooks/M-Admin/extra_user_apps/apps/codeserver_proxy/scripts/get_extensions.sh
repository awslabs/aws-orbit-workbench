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

# Go get the VSIX files that we cannot get from the markeplace directly
#workingDir=/home/jovyan/.local/share/code-server/CachedExtensionVSIXs
workingDir=$pwd
curl -fsSL https://marketplace.visualstudio.com/_apis/public/gallery/publishers/mtxr/vsextensions/sqltools-driver-pg/0.2.0/vspackage \
-o $workingDir/mtxr.sqltools-driver-pg-0.2.0.gz
gunzip $workingDir/mtxr.sqltools-driver-pg-0.2.0.gz
mv $workingDir/mtxr.sqltools-driver-pg-0.2.0 $workingDir/mtxr.sqltools-driver-pg-0.2.0.vsix
code-server --install-extension $workingDir/mtxr.sqltools-driver-pg-0.2.0.vsix --force