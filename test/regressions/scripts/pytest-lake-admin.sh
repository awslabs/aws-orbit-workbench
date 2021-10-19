#!/bin/bash

set -e
# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

# Set the .kube/config with respect to runtime environment
if [[ "${ENV_NAME}" == *"-iso"* ]]; then
    pytest -k "testlakeadmin and not testlakeadmin_noniso" -n auto --junitxml=regression_report.xml test_lake_admin.py

    if cat .pytest_cache/v/cache/lastfailed > /dev/null 2>&1; then
        echo -e "\nRetrying the last failed tests\n"
        pytest -k "testlakeadmin and not testlakeadmin_noniso" -n auto --junitxml=regression_report_last_failed.xml test_lake_admin.py
    fi
else
    pytest -k testlakeadmin -n auto --junitxml=regression_report.xml test_lake_admin.py

    if cat .pytest_cache/v/cache/lastfailed > /dev/null 2>&1; then
        echo -e "\nRetrying the last failed tests\n"
        pytest -k testlakeadmin -n auto --junitxml=regression_report_last_failed.xml test_lake_admin.py
    fi
fi