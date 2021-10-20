#!/bin/bash

set -e
# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

pytest -k testlakeuser -n auto --junitxml=regression_report.xml test_lake_user.py

if cat .pytest_cache/v/cache/lastfailed > /dev/null 2>&1; then
    pytest -k testlakeuser -n auto --junitxml=regression_report_last_failed.xml test_lake_user.py
fi