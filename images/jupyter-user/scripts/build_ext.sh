#!/usr/bin/env bash
set -x
if [ -d "extensions" ]; then
  echo "Building extension"
else
  echo "must be inside images/jupyter-user directory"
fi

# TODO ST Changing extension folder
#cd extensions/jupyterlab_orbit
cd ../../jupyterlab_orbit
jlpm run build --no-minimize --dev-build --source-map=True