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

set -x

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
ARCHIVE_DIR=${DIR}/aws-orbit_jupyter-user

rm -r ${ARCHIVE_DIR}
rm ${ARCHIVE_DIR}.tar.gz

mkdir -p ${ARCHIVE_DIR}

cp -r ${DIR}/python-utils ${ARCHIVE_DIR}/
cp -r ${DIR}/transformations ${ARCHIVE_DIR}/
cp -r ${DIR}/extensions ${ARCHIVE_DIR}/
cp ${DIR}/jupyter_server_config.py ${ARCHIVE_DIR}/
cp ${DIR}/requirements.txt ${ARCHIVE_DIR}/
cp ${DIR}/bootstrap.sh ${ARCHIVE_DIR}/
cp ${DIR}/bundle.sh ${ARCHIVE_DIR}/
cp ${DIR}/Dockerfile ${ARCHIVE_DIR}/
cp ${DIR}/VERSION ${ARCHIVE_DIR}/

touch ${ARCHIVE_DIR}/pip.conf

cd ${DIR}
tar czvf aws-orbit_jupyter-user.tar.gz ./aws-orbit_jupyter-user