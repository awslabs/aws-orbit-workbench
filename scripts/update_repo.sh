#!/bin/bash

set -ex

MODULE=$1
PACKAGE=$2

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

cd $DIR/../$MODULE

VERSION=$(cat VERSION)
rm dist/*
aws codeartifact login --tool twine --domain aws-orbit --repository python-repository

aws codeartifact delete-package-versions \
    --domain aws-orbit \
    --repository python-repository \
    --package $PACKAGE \
    --versions $VERSION \
    --format pypi

python setup.py bdist_wheel
twine upload --repository codeartifact dist/*
