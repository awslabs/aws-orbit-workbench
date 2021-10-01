#!/bin/bash

set -e

# Required os env variables. Replace with testing Orbit env details
# AWS_ORBIT_ENV, AWS_ORBIT_TEAM_SPACE

# Set the .kube/config with respect to runtime environment
pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_cleaner

# Multi threaded
pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_unzip -n auto

pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_check_data_files

# Multi threaded
pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_create_glue_tables -n auto

pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_check_glue_tables

pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_lf
