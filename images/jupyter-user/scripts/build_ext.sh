#!/usr/bin/env bash
set -x
if [ -d "extensions" ]; then
  echo "Building extension"
else
  echo "must be inside images/jupyter-user directory"
fi

cd ../../jupyterlab_orbit
jlpm run build --no-minimize --dev-build --source-map=True