#!/usr/bin/env bash


port=$1

# VSCode Extensions for extra_user_apps/codeserver 
if [ -d "/opt/orbit/apps/codeserver/extensions" ] && ! [ -d "/home/jovyan/.code-server/extensions" ]; then
    mkdir -p /home/jovyan/.code-server/extensions && \
    cp -r /opt/orbit/apps/codeserver/extensions /home/jovyan/.code-server
fi
if [ -d "/opt/orbit/apps/codeserver/CachedExtensionVSIXs" ] && ! [ -d "/home/jovyan/.code-server/CachedExtensionVSIXs" ]; then
    mkdir -p /home/jovyan/.code-server/CachedExtensionVSIXs && \
    cp -r /opt/orbit/apps/codeserver/CachedExtensionVSIXs /home/jovyan/.code-server
fi

# Populate an aws/credentials file base on the attached role
python3 /opt/orbit/codeserver_proxy/getcreds.py

# get the k8s info and create a config on start
#/opt/orbit/codeserver_proxy/create_kubeconfig.sh

# Start codeserver 
/opt/orbit/codeserver_proxy/start_codeserver.sh $1

