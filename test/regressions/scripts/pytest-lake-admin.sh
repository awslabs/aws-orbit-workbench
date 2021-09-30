#!/bin/bash

# set -e

# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

# Set the .kube/config with respect to runtime environment
pytest -c ./pytest.ini --kube-config ~/.kube/config -v -s  -k testlakeadmin -n auto --junitxml=regression_report.xml
