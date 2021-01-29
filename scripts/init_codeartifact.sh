#!/bin/bash

set -e

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars

aws codeartifact create-domain \
    --domain ${DOMAIN} \
    && echo "Created codeartifact domain: ${DOMAIN}" \
    || (echo "ERROR: Failed to create codeartifact domain: ${DOMAIN}"; exit 1)

aws codeartifact create-repository \
    --domain ${DOMAIN} \
    --repository ${REPOSITORY} \
    && echo "Created codeartifact repository: ${REPOSITORY}" \
    || (echo "ERROR: Failed to create codeartifact repository: ${REPOSITORY}"; exit 1)

aws codeartifact associate-external-connection \
    --domain ${DOMAIN} \
    --repository ${REPOSITORY} \
    --external-connection "public:pypi" \
    && echo "Associated external connection: public:pypi" \
    || (echo "ERROR: Failed to associate external connection: public:pypi"; exit 1)
