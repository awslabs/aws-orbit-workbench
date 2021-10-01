#!/bin/bash

#set -e

# Set the .kube/config with respect to runtime environment
export AWS_ORBIT_ENV='iter'
export AWS_ORBIT_TEAM_SPACE='lake-user'
pytest --rootdir . -c ./pytest.ini --kube-config ~/.kube/config -v -s  -k testlakeuser -n auto --junitxml=regression_report.xml test_lake_user.py

cat .pytest_cache/v/cache/lastfailed

if [[ $? -ne 0 ]]; then
    pytest --rootdir . -c ./pytest.ini --kube-config ~/.kube/config -v -s  -k testlakeuser -n auto --junitxml=regression_report.xml --lf test_lake_user.py
fi
