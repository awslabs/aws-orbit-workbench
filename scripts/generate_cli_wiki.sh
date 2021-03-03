#!/bin/bash

# pip install mkdocs and mkdocs-click
# Run from ./aws-orbit-workbench

ROOT_PATH=`pwd`
MKDOCS_FILE="${ROOT_PATH}/cli/site/index.html"
                
BEGINNING_SEARCH_STR='<h4 id="usage">Usage</h4>'
END_SEARCH_STR='</code></pre>'

cd "${ROOT_PATH}"/cli/
mkdocs build

if [[ $? -ne 0 ]]; then
    echo "There was an issue running 'mkdocs build'"
    exit 1
fi

BEGINNING_LINE_NUMBER=`grep -n "${BEGINNING_SEARCH_STR}" "${MKDOCS_FILE}" | cut -d ':' -f1 | head -n 1`
END_LINE_NUMBER=`grep -n "${END_SEARCH_STR}" "${MKDOCS_FILE}" | cut -d ':' -f1 | tail -n 1`

sed -n "${BEGINNING_LINE_NUMBER},${END_LINE_NUMBER}p" ${MKDOCS_FILE} > "${ROOT_PATH}"/cli/docs/Deploy-Custom-Docker-Images.md

GIT_TMP_PATH="${ROOT_PATH}/cli/tmp"

mkdir "${GIT_TMP_PATH}"
git clone https://github.com/awslabs/aws-orbit-workbench.wiki.git "${GIT_TMP_PATH}"

cp "${ROOT_PATH}"/cli/docs/Deploy-Custom-Docker-Images.md "${GIT_TMP_PATH}"

cd "${GIT_TMP_PATH}"
git add Deploy-Custom-Docker-Images.md
git commit -m 'Updated CLI info'
git push

rm -rf "${GIT_TMP_PATH}"
rm "${ROOT_PATH}"/cli/docs/Deploy-Custom-Docker-Images.md
