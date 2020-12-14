#!/bin/bash

set -x

VERSION=$(cat VERSION)
rm dist/*
aws codeartifact login --tool twine --domain aws-datamaker --repository python-repository

aws codeartifact delete-package-versions \
    --domain aws-datamaker \
    --repository python-repository \
    --package datamaker-cli \
    --versions $VERSION \
    --format pypi

python setup.py bdist_wheel
twine upload --repository codeartifact dist/*
