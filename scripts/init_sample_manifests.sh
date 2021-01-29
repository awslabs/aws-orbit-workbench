#!/bin/bash

set -e

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars


mkdir ${CONF_DIR} \
    && echo "Created ${CONF_DIR}" \
    || (echo "ERROR: Failed to create ${CONF_DIR}"; exit 1)

cp ${SAMPLES_DIR}/manifests/minimal/* ${CONF_DIR}/ \
    && echo "Copied ${SAMPLES_DIR}/manifests/minimal/* to ${CONF_DIR}/" \
    || (echo "ERROR: Failed to copy ${SAMPLES_DIR}/manifests/minimal/* to ${CONF_DIR}/"; exit 1)
cp ${SAMPLES_DIR}/manifests/plugins/* ${CONF_DIR}/ \
    && echo "Copied ${SAMPLES_DIR}/manifests/plugins/* ${CONF_DIR}/" \
    || (echo "ERROR: Failed to copy ${SAMPLES_DIR}/manifests/plugins/* ${CONF_DIR}/"; exit 1)
