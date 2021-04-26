#!/usr/bin/env bash


port=$1
echo $port
code-server --bind-addr localhost:$port --auth none \
--user-data-dir /home/jovyan/private --config /home/jovyan/private/.config/code-server/config.yaml

