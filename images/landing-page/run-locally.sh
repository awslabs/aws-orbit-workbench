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

export ENV_NAME=env
export USER_POOL_ID=us-east-1_ILHCWP974
export USER_POOL_CLIENT_ID=6orcm1n6lqvhb02ubog5jebid7
export IDENTITY_POOL_ID=us-east-1:c84fb456-75d8-482e-a5ed-6ece7c03d6ae
export REGION=$(aws configure get region)

content="
window.REACT_APP_ENV_NAME='$ENV_NAME';
window.REACT_APP_USER_POOL_ID='$USER_POOL_ID';
window.REACT_APP_USER_POOL_CLIENT_ID='$USER_POOL_CLIENT_ID';
window.REACT_APP_IDENTITY_POOL_ID='$IDENTITY_POOL_ID';
window.REACT_APP_REGION='$REGION';
"
echo "$content" > public/config.js

yarn start
