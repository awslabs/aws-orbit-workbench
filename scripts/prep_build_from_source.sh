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
    ${DIR}/update_repo.sh plugins/emr_on_eks aws-orbit-emr-on-eks \
        && echo "Updated custom_cfn codeartifact repository" \
        || (echo "ERROR: Failed to update custom_cfn codeartifact repository"; exit 1)
    ${DIR}/update_repo.sh plugins/code_commit aws-orbit-code-commit \
        && echo "Updated code_commit codeartifact repository" \
        || (echo "ERROR: Failed to update code_commit codeartifact repository"; exit 1)
    ${DIR}/update_repo.sh plugins/hello_world aws-orbit-hello-world \
        && echo "Updated SDK codeartifact repository" \
        || (echo "ERROR: Failed to update SDK codeartifact repository"; exit 1)
    ${DIR}/update_repo.sh plugins/redshift aws-orbit-redshift \
        && echo "Updated redshift codeartifact repository" \
        || (echo "ERROR: Failed to update redshift codeartifact repository"; exit 1)
    ${DIR}/update_repo.sh plugins/team_script_launcher aws-orbit-team-script-launcher \
        && echo "Updated team_script_launcher codeartifact repository" \
        || (echo "ERROR: Failed to update team_script_launcher codeartifact repository"; exit 1)
    ${DIR}/update_repo.sh plugins/custom_cfn aws-orbit-custom-cfn \
        && echo "Updated custom_cfn codeartifact repository" \
        || (echo "ERROR: Failed to update custom_cfn codeartifact repository"; exit 1)
    ${DIR}/update_repo.sh plugins/ray aws-orbit-ray \
        && echo "Updated ray codeartifact repository" \
        || (echo "ERROR: Failed to update ray codeartifact repository"; exit 1)
    ${DIR}/update_repo.sh plugins/lustre aws-orbit-lustre \
        && echo "Updated lustre codeartifact repository" \
        || (echo "ERROR: Failed to update lustre codeartifact repository"; exit 1)

fi