#!/bin/bash

set -e
# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

# Set the .kube/config with respect to runtime environment
pytest -k testlakecreator -n auto --junitxml=regression_report.xml

cat .pytest_cache/v/cache/lastfailed

if [[ $? -ne 0 ]]; then
    pytest -k testlakecreator -n auto --junitxml=regression_report.xml --lf
fi