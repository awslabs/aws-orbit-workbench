#!/usr/bin/env bash


port=$1
echo $port
export PATH="/opt/orbit/apps/codeserver/bin:$PATH"

code-server --bind-addr localhost:$port --auth none \
--user-data-dir /home/jovyan/private/code-server \
--config /home/jovyan/private/code-server/.config/code-server/config.yaml

