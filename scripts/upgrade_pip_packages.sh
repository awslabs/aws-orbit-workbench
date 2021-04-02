#!/bin/bash

set -e

# Run from the root directory #

ROOT_PATH=`pwd`

# Paths where pip-compile generates requirements files #
paths=(
    "${ROOT_PATH}/cli"
    "${ROOT_PATH}/images/jupyter-user/extensions/jupyterlab_orbit"
    "${ROOT_PATH}/plugins/code_commit"
    "${ROOT_PATH}/plugins/hello_world"
    "${ROOT_PATH}/plugins/redshift"
    "${ROOT_PATH}/plugins/team_script_launcher"
    "${ROOT_PATH}/plugins/custom_cfn"
    "${ROOT_PATH}/plugins/emr_on_eks"
    "${ROOT_PATH}/sdk"
)

UPGRADE=""
SED=${SED:-sed}

while [ $# -gt 0 ] 
do
    case $1 in
        --gsed)
        SED="gsed"
        shift # Remove --upgrade from processing
        ;;
        --upgrade)
        UPGRADE="--upgrade"
        shift # Remove --upgrade from processing
        ;;
        --path)
        paths=("${ROOT_PATH}/${2}")
        shift # Remove --path from processing
        ;;
    esac
    shift
done


for path in "${paths[@]}"; do
    cd $path

    pip-compile ${UPGRADE}
    pip-compile ${UPGRADE} -r requirements-dev.in

    ${SED} -i "s|file://$path|.|g" requirements-dev.txt

    if [[ "${path}" == *"plugins"* ]]; then
        ${SED} -i "s|file://$ROOT_PATH|../..|g" requirements-dev.txt
    else
        ${SED} -i "s|file://$ROOT_PATH|..|g" requirements-dev.txt
    fi
done
