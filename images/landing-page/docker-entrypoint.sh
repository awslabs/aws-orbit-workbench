#!/usr/bin/env sh
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

content="
window.REACT_APP_ENV_NAME='$ENV_NAME';
window.REACT_APP_USER_POOL_ID='$USER_POOL_ID';
window.REACT_APP_USER_POOL_CLIENT_ID='$USER_POOL_CLIENT_ID';
window.REACT_APP_IDENTITY_POOL_ID='$IDENTITY_POOL_ID';
window.REACT_APP_REGION='$AWS_DEFAULT_REGION';

window.REACT_APP_EXTERNAL_IDP='$COGNITO_EXTERNAL_PROVIDER';
window.REACT_APP_EXTERNAL_IDP_LABEL='$COGNITO_EXTERNAL_PROVIDER_LABEL';
window.REACT_APP_EXTERNAL_DOMAIN='$COGNITO_EXTERNAL_PROVIDER_DOMAIN';
window.REACT_APP_EXTERNAL_REDIRECT='$COGNITO_EXTERNAL_PROVIDER_REDIRECT';
"
echo "$content" > /usr/share/nginx/html/config.js
nginx -g "daemon off;"
