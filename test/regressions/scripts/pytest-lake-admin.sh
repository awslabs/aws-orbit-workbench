#!/bin/bash

set -e
# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

# Set the .kube/config with respect to runtime environment
if [[ "${ENV_NAME}" == *"-iso"* ]]; then
    pytest -k "testlakeadmin and not testlakeadmin_noniso" -n auto --junitxml=regression_report.xml test_lake_admin.py

    cat .pytest_cache/v/cache/lastfailed || echo "No failed test"

    pytest -k "testlakeadmin and not testlakeadmin_noniso" -n auto --junitxml=regression_report_last_failed.xml test_lake_admin.py
else
    pytest -k testlakeadmin -n auto --junitxml=regression_report.xml test_lake_admin.py

    cat .pytest_cache/v/cache/lastfailed || echo "No failed test"

    pytest -k testlakeadmin -n auto --junitxml=regression_report_last_failed.xml test_lake_admin.py
fi