#!/bin/bash

set -x

VERSION=$(cat VERSION)
rm dist/*
aws codeartifact login --tool twine --domain aws-orbit --repository python-repository

aws codeartifact delete-package-versions \
    --domain aws-orbit \
    --repository python-repository \
    --package aws-orbit-sdk \
    --versions $VERSION \
    --format pypi

python setup.py bdist_wheel
twine upload --repository codeartifact dist/*
