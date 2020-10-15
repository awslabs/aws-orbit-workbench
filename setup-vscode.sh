#!/usr/bin/env bash
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
set -e

./setup.sh

code --install-extension DavidAnson.vscode-markdownlint
code --install-extension Okteto.kubernetes-context
code --install-extension VisualStudioExptTeam.vscodeintellicode
code --install-extension be5invis.toml
code --install-extension donjayamanne.githistory
code --install-extension ms-azuretools.vscode-docker
code --install-extension ms-kubernetes-tools.vscode-kubernetes-tools
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension redhat.vscode-yaml
code --install-extension twixes.pypi-assistant
code --install-extension aws-scripting-guy.cform
code --install-extension kddejong.vscode-cfn-lint

python_path=$(which python)
cfn_lint_path="$(dirname $python_path)/cfn-lint"

vscode_settings='{
  "cfnLint.path": "'$cfn_lint_path'",
  "cfnLint.ignoreRules": ["E1029", "E3031"],
  "explorer.autoReveal": false,
  "files.autoSave": "onFocusChange",
  "files.exclude": {
    "**/*.egg-info": true,
    "**/__pycache__/": true,
  },
  "outline.showArrays": false,
  "outline.showConstants": false,
  "outline.showFields": false,
  "outline.showKeys": false,
  "outline.showNull": false,
  "outline.showStrings": false,
  "outline.showTypeParameters": false,
  "outline.showVariables": false,
  "python.analysis.extraPaths": [
    "cli/",
    "images/jupyter-hub/utils/",
    "images/jupyter-user/schedule/schedule/",
    "images/jupyter-user/sdk/",
  ],
  "python.analysis.memory.keepLibraryAst": true,
  "python.formatting.blackArgs": ["--line-length 120", "--target-version py36"],
  "python.formatting.provider": "black",
  "python.languageServer": "Pylance",
  "python.linting.enabled": true,
  "python.linting.flake8Args": ["--max-line-length 120"],
  "python.linting.flake8Enabled": true,
  "python.linting.mypyCategorySeverity.error": "Hint",
  "python.linting.mypyCategorySeverity.note": "Hint",
  "python.linting.mypyEnabled": true,
  "python.linting.pylintEnabled": false,
  "python.pythonPath": "'$python_path'",
  "python.terminal.activateEnvironment": true,
  "workbench.editor.labelFormat": "default",
  "workbench.tree.indent": 16,
  "yaml.customTags": [
    "!Equals sequence",
    "!FindInMap sequence",
    "!GetAtt",
    "!GetAZs",
    "!ImportValue",
    "!Join sequence",
    "!Ref",
    "!Select sequence",
    "!Split sequence",
    "!Sub"
  ]
}
'

rm -rf .vscode
mkdir .vscode
echo "$vscode_settings" > .vscode/settings.json
