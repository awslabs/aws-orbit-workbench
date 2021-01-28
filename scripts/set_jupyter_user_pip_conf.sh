#!/bin/bash

set -ex

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

aws codeartifact login --tool pip --domain aws-orbit --repository python-repository
cp ~/.config/pip/pip.conf $DIR/../images/jupyter-user/
