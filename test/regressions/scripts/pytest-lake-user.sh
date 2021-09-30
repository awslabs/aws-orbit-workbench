#!/bin/bash

set -e

# Required os env variables. Replace with testing Orbit env details
export AWS_ORBIT_ENV=iter
export AWS_ORBIT_TEAM_SPACE=lake-user

# Set the .kube/config with respect to runtime environment
pytest --kube-config /Users/stthoom/.kube/config -v -s  -k testlakeuser -n auto