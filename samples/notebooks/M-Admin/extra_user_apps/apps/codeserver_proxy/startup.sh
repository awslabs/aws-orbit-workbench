#!/usr/bin/env bash


port=$1

# VSCode Extensions for extra_user_apps/codeserver 
if [ -d "/home/jovyan/.local/share/code-server/CachedExtensionVSIXs" ] && ! [ -d "/home/jovyan/private/CachedExtensionVSIXs" ]; then
  ln -s /home/jovyan/.local/share/code-server/CachedExtensionVSIXs /home/jovyan/private/CachedExtensionVSIXs
fi
if [ -d "/home/jovyan/.local/share/code-server/extensions" ] && ! [ -d "/home/jovyan/private/extensions" ]; then
  ln -s /home/jovyan/.local/share/code-server/extensions /home/jovyan/private/extensions
fi

# Populate an aws/credentials file base on the attached role
python3 /home/jovyan/.orbit/apps/codeserver_proxy/getcreds.py

# Start codeserver 
chmod +x /home/jovyan/.orbit/apps/codeserver_proxy/start_codeserver.sh
/home/jovyan/.orbit/apps/codeserver_proxy/start_codeserver.sh $1

