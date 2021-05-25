#!/usr/bin/env bash


port=$1

# VSCode Extensions for extra_user_apps/codeserver 
if [ -d "/home/jovyan/.local/share/code-server/CachedExtensionVSIXs" ] && ! [ -d "/home/jovyan/private/CachedExtensionVSIXs" ]; then
  #ln -s /home/jovyan/.local/share/code-server/CachedExtensionVSIXs /home/jovyan/private/CachedExtensionVSIXs
  cp /home/jovyan/.local/share/code-server/CachedExtensionVSIXs /home/jovyan/private/ -r
fi
if [ -d "/home/jovyan/.local/share/code-server/extensions" ] && ! [ -d "/home/jovyan/private/extensions" ]; then
  #ln -s /home/jovyan/.local/share/code-server/extensions /home/jovyan/private/extensions
  cp /home/jovyan/.local/share/code-server/extensions /home/jovyan/private/ -r
fi

# Populate an aws/credentials file base on the attached role
python3 /opt/orbit/codeserver_proxy/getcreds.py

# get the k8s info and create a config on start
/opt/orbit/codeserver_proxy/create_kubeconfig.sh

# Start codeserver 
/opt/orbit/codeserver_proxy/start_codeserver.sh $1

