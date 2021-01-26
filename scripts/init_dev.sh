#!/bin/bash

set -ex

DOMAIN="aws-orbit"
REPOSITORY="python-repository"

aws codeartifact create-domain \
    --domain $DOMAIN

aws codeartifact create-repository \
    --domain $DOMAIN \
    --repository $REPOSITORY

aws codeartifact associate-external-connection \
    --doman $DOMAIN \
    --repository $REPOSITORY \
    --external-connection "public:pypi"
