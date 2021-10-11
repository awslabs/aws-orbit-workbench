#!/bin/bash

set -e

# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

# Set the .kube/config with respect to runtime environment

pytest -k lakecreator_cleaner test_lake_creator_cleaner.py


# Multi threaded
pytest -k testlakecreator_unzip -n auto test_lake_creator.py

pytest -k testlakecreator_check_data_files test_lake_creator.py

# Multi threaded
pytest -k testlakecreator_create_glue_tables -n auto test_lake_creator.py

pytest -k testlakecreator_check_glue_tables test_lake_creator.py

pytest -k testlakecreator_lf test_lake_creator.py
