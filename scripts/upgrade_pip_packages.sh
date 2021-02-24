#!/bin/bash

# Run from the root directory #

ROOT_PATH=`pwd`

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

    # Where {1} is a cli arg. In our case, --upgrade, for the periodic task of upgrading all packages
    pip-compile ${1}
    pip-compile ${1} -r requirements-dev.in
    
    sed -i "s|file://$path|.|g" requirements-dev.txt
    sed -i "/^--index-url.*$/d" requirements.txt requirements-dev.txt
    sed -i '/^$/d' requirements.txt requirements-dev.txt

    if [[ "${path}" == *"plugins"* ]]; then
        sed -i "s|file://$ROOT_PATH|../..|g" requirements-dev.txt
    else
        sed -i "s|file://$ROOT_PATH|..|g" requirements-dev.txt
    fi
done