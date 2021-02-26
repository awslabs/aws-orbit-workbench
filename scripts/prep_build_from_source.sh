#!/bin/bash

set -e

source $( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )/vars

${DIR}/set_jupyter_user_pip_conf.sh \
    && echo "Set jupyter-user pip.conf" \
    || (echo "ERROR: Failed to set jupyter-user pip.conf"; exit 1)
${DIR}/update_repo.sh cli ${DOMAIN} \
    && echo "Updated CLI codeartifact repository" \
    || (echo "ERROR: Failed to update CLI codeartifact repository"; exit 1)
# ${DIR}/update_repo.sh sdk ${DOMAIN}-sdk \
#     && echo "Updated SDK codeartifact repository" \
#     || (echo "ERROR: Failed to update SDK codeartifact repository"; exit 1)

# Adding plugins to Codeartifact
# ${DIR}/update_repo.sh plugins/code_commit aws-orbit-code-commit \
#     && echo "Updated code_commit codeartifact repository" \
#     || (echo "ERROR: Failed to update code_commit codeartifact repository"; exit 1)
# ${DIR}/update_repo.sh plugins/hello_world aws-orbit-hello-world \
#     && echo "Updated SDK codeartifact repository" \
#     || (echo "ERROR: Failed to update SDK codeartifact repository"; exit 1)
# ${DIR}/update_repo.sh plugins/redshift aws-orbit-redshift \
#     && echo "Updated redshift codeartifact repository" \
#     || (echo "ERROR: Failed to update redshift codeartifact repository"; exit 1)
# ${DIR}/update_repo.sh plugins/team_script_launcher aws-orbit-team-script-launcher \
#     && echo "Updated team_script_launcher codeartifact repository" \
#     || (echo "ERROR: Failed to update team_script_launcher codeartifact repository"; exit 1)