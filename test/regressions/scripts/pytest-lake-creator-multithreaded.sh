#!/bin/bash

set -e

# Required os env variables. Replace with testing Orbit env details
export AWS_ORBIT_ENV=iter
export AWS_ORBIT_TEAM_SPACE=lake-creator

# Set the .kube/config with respect to runtime environment
pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_cleaner

# Multi threaded
pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_zip -n auto

pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_unzip_check

# Multi threaded
pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_glue -n auto

pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_checkglue

pytest --kube-config ~/.kube/config -v -s  -k testlakecreator_lf
