#!/bin/bash

set -e

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars

CLI=0
SDK=0
PLUGINS=0

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
        --all)
        CLI=1
        SDK=1
        PLUGINS=1
        shift # Remove --sdk from processing
        ;;
    esac
done

${DIR}/set_jupyter_user_pip_conf.sh \
    && echo "Set jupyter-user pip.conf" \
    || (echo "ERROR: Failed to set jupyter-user pip.conf"; exit 1)

if [ $CLI -eq 1 ]; then
    ${DIR}/update_repo.sh cli ${DOMAIN} \
        && echo "Updated CLI codeartifact repository" \
        || (echo "ERROR: Failed to update CLI codeartifact repository"; exit 1)
fi

if [ $SDK -eq 1 ]; then
    ${DIR}/update_repo.sh sdk ${DOMAIN}-sdk \
        && echo "Updated SDK codeartifact repository" \
        || (echo "ERROR: Failed to update SDK codeartifact repository"; exit 1)
fi

if [ $PLUGINS -eq 1 ]; then
    # Adding plugins to Codeartifact
    PLUGINS_DIR="${DIR}/../plugins"
    ORBIT_PREFIX="aws-orbit-"

    for module in `ls "${PLUGINS_DIR}"`
    do
        MODULE_NAME_FORMATTED=`echo ${module} | sed "s/_/-/g"`
        MODULE_PKG="${ORBIT_PREFIX}${MODULE_NAME_FORMATTED}"

        ${DIR}/update_repo.sh plugins/"${module}" "${MODULE_PKG}" \
            && echo "Updated $module codeartifact repository" \
            || (echo "ERROR: Failed to update $module codeartifact repository"; exit 1)
    done
fi