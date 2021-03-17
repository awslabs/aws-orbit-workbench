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
pip install -U pip
pip install -r requirements-dev.txt
cd extensions/jupyterlab_orbit
pip install -e .

jlpm install
jupyter labextension develop . --overwrite
cd ../..

mkdir -p .workspace
mkdir -p .workspace/shared
mkdir -p .workspace/private
ln -sf ../../../../samples .workspace/shared/samples

pip install --no-deps jupyterhub-kubespawner~=0.15.0
echo "" > `pip  show jupyterhub-kubespawner | grep "Location:" | cut -d ':' -f 2`/kubespawner/__init__.py
