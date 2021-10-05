#!/bin/bash

set -e

# Required os env variables. Replace with testing Orbit env details
# export AWS_ORBIT_ENV=iter
# export AWS_ORBIT_TEAM_SPACE=lake-creator

# Set the .kube/config with respect to runtime environment
pytest -k lakecreatorcleaner test_lake_creator.py

# Multi threaded
pytest -k testlakecreator_zip -n auto test_lake_creator.py

pytest -k testlakecreator_unzip_check test_lake_creator.py

# Multi threaded
pytest -k testlakecreator_glue -n auto test_lake_creator.py

pytest -k testlakecreator_checkglue test_lake_creator.py

pytest -k testlakecreator_lf test_lake_creator.py
