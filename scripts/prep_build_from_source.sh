#!/bin/bash

set -e

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars

CLI=0
SDK=0
PLUGINS=0
LAB=0
IGNORE_TWINE_ERROR=1

for ARG in "$@"
do
    case $ARG in
        --cli)
        CLI=1
        shift # Remove --cli from processing
        ;;
        --sdk)
        SDK=1
        shift # Remove --sdk from processing
        ;;
        --plugins)
        PLUGINS=1
        shift # Remove --sdk from processing
        ;;
        --lab)
        LAB=1
        shift # Remove --lab from processing
        ;;
        --ignore-twine-error)
        IGNORE_TWINE_ERROR=0
        shift # Remove --ignore-twine-error from processing
        ;;
        --all)
        CLI=1
        SDK=1
        PLUGINS=1
        LAB=1
        shift # Remove --sdk from processing
        ;;
    esac
done

${DIR}/set_jupyter_user_pip_conf.sh \
    && echo "Set jupyter-user pip.conf" \
    || (echo "ERROR: Failed to set jupyter-user pip.conf"; exit 1)

if [ $CLI -eq 1 ]; then
    ${DIR}/update_repo.sh cli ${DOMAIN} ${IGNORE_TWINE_ERROR} \
        && echo "Updated CLI codeartifact repository" \
        || (echo "ERROR: Failed to update CLI codeartifact repository"; exit 1)
fi

if [ $SDK -eq 1 ]; then
    ${DIR}/update_repo.sh sdk ${DOMAIN}-sdk ${IGNORE_TWINE_ERROR} \
        && echo "Updated SDK codeartifact repository" \
        || (echo "ERROR: Failed to update SDK codeartifact repository"; exit 1)
fi

if [ $LAB -eq 1 ]; then
    ${DIR}/update_repo.sh jupyterlab_orbit ${DOMAIN}-jupyterlab-orbit ${IGNORE_TWINE_ERROR} \
        && echo "Updated Jupyterlab-orbit codeartifact repository" \
        || (echo "ERROR: Failed to update Jupyterlab-orbit codeartifact repository"; exit 1)
fi

if [ $PLUGINS -eq 1 ]; then
    # Adding plugins to Codeartifact
    PLUGINS_DIR="${DIR}/../plugins"
    ORBIT_PREFIX="aws-orbit-"

    for module in `ls "${PLUGINS_DIR}"`
    do
        MODULE_NAME_FORMATTED=`echo ${module} | sed "s/_/-/g"`
        MODULE_PKG="${ORBIT_PREFIX}${MODULE_NAME_FORMATTED}"

        ${DIR}/update_repo.sh plugins/"${module}" "${MODULE_PKG}" ${IGNORE_TWINE_ERROR} \
            && echo "Updated $module codeartifact repository" \
            || (echo "ERROR: Failed to update $module codeartifact repository"; exit 1)
    done
fi