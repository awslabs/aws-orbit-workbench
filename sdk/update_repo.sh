#!/bin/bash

set -x

VERSION=$(cat VERSION)
rm dist/*

aws codeartifact delete-package-versions \
    --domain aws-orbit \
    --repository python-repository \
    --package orbit-sdk \
    --versions $VERSION \
    --format pypi

python setup.py bdist_wheel
twine upload --repository codeartifact dist/*
