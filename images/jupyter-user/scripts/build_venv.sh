#!/usr/bin/env bash
set -x

if [ -d "extensions" ]; then
  echo "Building venv for jupyter user"
else
  echo "must be inside images/jupyter-user directory"
fi

if [ -d ".venv" ]; then
  echo "Updating .venv"
else
  echo "creating .venv"
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements-dev.txt
cd extensions/jupyterlab_orbit
jupyter labextension develop . --overwrite
mkdir -p .workspace
mkdir -p .workspace/shared
mkdir -p .workspace/private
ln -s ../../../../samples .workspace/shared/samples
