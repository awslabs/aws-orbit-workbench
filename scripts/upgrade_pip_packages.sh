#!/bin/bash

set -e

# Run from the root directory #

ROOT_PATH=`pwd`

# Paths where pip-compile generates requirements files #
paths=(
    "${ROOT_PATH}/cli"
    "${ROOT_PATH}/jupyterlab_orbit"
    "${ROOT_PATH}/sdk"
)

for module in `ls ${ROOT_PATH}/plugins`; do
    paths+=("${ROOT_PATH}/plugins/$module")
done

UPGRADE=""
SED=${SED:-sed}
CLEAN="no"

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
        --clean)
        CLEAN="yes"
        shift # Remove --clean from processing
        ;;
    esac
done


for path in "${paths[@]}"; do
    echo
    echo "Updating requirements for ${path}"
    cd $path

    if [[ $CLEAN == "yes" ]]; then
        echo " - Cleaning requirements files"
        rm -f requirements.txt requirements-dev.txt
    fi

    echo " - Updating module dependencies"
    pip-compile ${UPGRADE} --quiet --rebuild
    echo " - Updating module development dependencies"
    pip-compile ${UPGRADE} --quiet --rebuild requirements-dev.in

    echo " - Replacing full paths with relative paths"
    ${SED} -i "s|file://$path|.|g" requirements-dev.txt

    if [[ "${path}" == *"plugins"* ]]; then
        ${SED} -i "s|file://$ROOT_PATH|../..|g" requirements-dev.txt
    else
        ${SED} -i "s|file://$ROOT_PATH|..|g" requirements-dev.txt
    fi
done
