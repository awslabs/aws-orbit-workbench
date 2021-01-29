#!/bin/bash

set -e

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars

aws codeartifact login --tool pip --domain ${DOMAIN} --repository ${REPOSITORY} \
    && echo "Logged in to codeartifact domain/repository: ${DOMAIN}/${REPOSITORY}" \
    || (echo "ERROR: Failed to login to codeartifact domain/repository: ${DOMAIN}/${REPOSITORY}"; exit 1)
cp ~/.config/pip/pip.conf ${IMAGES_DIR}/jupyter-user/ \
    && echo "Copied ~/.config/pip/pip.conf to ${IMAGES_DIR}/jupyter-user/" \
    || (echo "ERROR: Failed to copy ~/.config/pip/pip.conf to ${IMAGES_DIR}/jupyter-user/"; exit 1)
