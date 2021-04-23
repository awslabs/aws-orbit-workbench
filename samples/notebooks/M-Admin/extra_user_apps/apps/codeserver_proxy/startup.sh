#!/usr/bin/env bash


port=$1

#chmod +x /home/jovyan/.orbit/apps/codeserver_proxy/getcreds.sh
chmod +x /home/jovyan/.orbit/apps/codeserver_proxy/start_codeserver.sh

python3 /home/jovyan/.orbit/apps/codeserver_proxy/getcreds.py
/home/jovyan/.orbit/apps/codeserver_proxy/start_codeserver.sh $1

