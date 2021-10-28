#!/bin/bash

set -e

# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

# Set the .kube/config with respect to runtime environment

pytest -k lakecreator_cleaner --junitxml=regression_report_cleaner.xml test_lake_creator_cleaner.py


# Multi threaded
pytest -k testlakecreator_unzip --junitxml=regression_report_unzip.xml test_lake_creator.py

pytest -k testlakecreator_check_data_files --junitxml=regression_report_checkdatafiles.xml test_lake_creator.py

# Multi threaded
pytest -k testlakecreator_create_glue_tables --junitxml=regression_report_creategluetables.xml test_lake_creator.py

pytest -k testlakecreator_check_glue_tables --junitxml=regression_report_checkgluetables.xml test_lake_creator.py 

pytest -k testlakecreator_lf --junitxml=regression_report_lf.xml test_lake_creator.py 
