#!/bin/bash

set -x

docker build --tag aws-datamaker-jupyter-user:latest .
docker tag aws-datamaker-jupyter-user:latest 011316101677.dkr.ecr.us-west-2.amazonaws.com/datamaker-dev-env-jupyter-user:latest
docker push 011316101677.dkr.ecr.us-west-2.amazonaws.com/datamaker-dev-env-jupyter-user:latest

