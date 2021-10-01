#!/bin/bash

set -e
# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

pytest -k testlakeuser -n auto --junitxml=regression_report.xml test_lake_user.py

cat .pytest_cache/v/cache/lastfailed

if [[ $? -ne 0 ]]; then
    pytest -k testlakeuser -n auto --junitxml=regression_report.xml --lf test_lake_user.py
fi
