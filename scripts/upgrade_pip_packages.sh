#!/bin/bash

# Run from the root directory #

ROOT_PATH=`pwd`
SED=${SED:-sed}

# Paths where pip-compile generates requirements files #
paths=(
    "${ROOT_PATH}/cli"
    "${ROOT_PATH}/plugins/code_commit"
    "${ROOT_PATH}/plugins/hello_world"
    "${ROOT_PATH}/plugins/redshift"
    "${ROOT_PATH}/plugins/team_script_launcher"
    "${ROOT_PATH}/sdk"
)

for path in "${paths[@]}"; do
    cd $path

    pip-compile ${1}
    pip-compile ${1} -r requirements-dev.in

    ${SED} -i "s|file://$path|.|g" requirements-dev.txt

    if [[ "${path}" == *"plugins"* ]]; then
        ${SED} -i "s|file://$ROOT_PATH|../..|g" requirements-dev.txt
    else
        ${SED} -i "s|file://$ROOT_PATH|..|g" requirements-dev.txt
    fi
done