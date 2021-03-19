#!/usr/bin/env bash
set -x

if [[ -z "$AWS_ORBIT_ENV" ]]; then
    echo "Must provide AWS_ORBIT_ENV in environment" 1>&2
    exit 1
fi

if [[ -z "$AWS_ORBIT_TEAM_SPACE" ]]; then
    echo "Must provide AWS_ORBIT_TEAM_SPACE in environment" 1>&2
    exit 1
fi

if [[ -z "$AWS_DEFAULT_REGION" ]]; then
    echo "Must provide AWS_DEFAULT_REGION in environment" 1>&2
    exit 1
fi
if [[ -z "$JUPYTERHUB_USER" ]]; then
    echo "Must provide JUPYTERHUB_USER in environment" 1>&2
    exit 1
fi


if [ -d "extensions" ]; then
  echo "Starting Jupyter lab"
else
  echo "must be inside images/jupyter-user directory"
fi

jupyter lab --notebook-dir=.workspace