#!/bin/bash

set -ex

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars

MODULE=$1
PACKAGE=$2

cd ${DIR}/../$MODULE \
    && echo "Changed directory to ${PWD}" \
    || echo "ERROR: Failed to change directory to ${PWD}"

VERSION=$(cat VERSION)
rm dist/* && echo "Removed dist/" || echo "No dist/ to delete"

aws codeartifact login --tool twine --domain ${DOMAIN} --repository ${REPOSITORY} \
    && echo "Logged in to codeartifact domain/repository: ${DOMAIN}/${REPOSITORY}" \
    || (echo "ERROR: Failed to login to codeartifact domain/repository: ${DOMAIN}/${REPOSITORY}"; exit 1)

aws codeartifact delete-package-versions \
    --domain ${DOMAIN} \
    --repository ${REPOSITORY} \
    --package ${PACKAGE} \
    --versions ${VERSION} \
    --format pypi \
    && echo "Deleted codeartifact package version: ${DOMAIN}/${REPOSITORY}/${PACKAGE}/${VERSION}" \
    || echo "Checked for codeartifact package version: ${DOMAIN}/${REPOSITORY}/${PACKAGE}/${VERSION}"

python setup.py bdist_wheel \
    && echo "Built python wheel" \
    || (echo "ERROR: Failed to build python wheel"; exit 1)
echo "Sleeping briefly"
sleep 3
twine upload --repository codeartifact dist/* \
    && echo "Twine upload successful" \
    || (echo "ERROR: Twine upload failed, this may be an eventual consistency issue (Try it again)"; exit 1)
