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

#!/usr/bin/env bash
set -ex

if [[ -z "$AWS_ORBIT_ENV" ]]; then
    echo "Must provide AWS_ORBIT_ENV in environment" 1>&2
    exit 1
fi

if [[ -z "$AWS_ORBIT_TEAM_SPACE" ]]; then
    echo "Must provide AWS_ORBIT_TEAM_SPACE in environment" 1>&2
    exit 1
fi

if [[ -z "$AWS_DEFAULT_REGION" ]]; then
    echo "Must provide AWS_DEFAULT_REGION in environment" 1>&2
    exit 1
fi

if [[ -z "$AWS_SECRET_ACCESS_KEY" ]]; then
    echo "Must provide AWS_SECRET_ACCESS_KEY in environment" 1>&2
    exit 1
fi

if [[ -z "$AWS_ACCESS_KEY_ID" ]]; then
    echo "Must provide AWS_ACCESS_KEY_ID in environment" 1>&2
    exit 1
fi
if [[ -z "$AWS_SESSION_TOKEN" ]]; then
    echo "Must provide AWS_SESSION_TOKEN in environment" 1>&2
    exit 1
fi


if [ -d "extensions" ]; then
  echo "Starting Jupyter lab"
else
  echo "must be inside images/jupyter-user directory"
fi

docker run \
    -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
    -e AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN} \
    -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
    -e AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION} \
    -e AWS_ORBIT_TEAM_SPACE=$AWS_ORBIT_TEAM_SPACE \
    -e AWS_ORBIT_ENV=$AWS_ORBIT_ENV \
    -p 8888:8888 \
    --rm \
    -it \
    jupyter-user
