#!/bin/bash

set -x

VERSION=$(cat VERSION)
rm dist/*

aws codeartifact delete-package-versions \
    --domain aws-datamaker \
    --repository python-repository \
    --package datamaker-sdk \
    --versions $VERSION \
    --format pypi

python setup.py bdist_wheel
twine upload --repository codeartifact dist/*
