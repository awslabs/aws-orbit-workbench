#!/usr/bin/env bash


port=$1
echo $port
export PATH="/opt/orbit/apps/codeserver/bin:$PATH"

DRIVER_DIR="/home/jovyan/shared/drivers"
INSTALL_FLAG="/home/jovyan/.code-server/INSTALLED_DRIVERS"
if [ -d "${DRIVER_DIR}" ] && ! [ -f "${INSTALL_FLAG}" ];then
    for driver in `ls "${DRIVER_DIR}" | grep .vsix`
    do
        echo "Installing ${driver}"
        echo $driver
        code-server --install-extension ${DRIVER_DIR}/${driver} \
        --extensions-dir /home/jovyan/.code-server/extensions --force \
        --user-data-dir /home/jovyan/.code-server \
        --config /home/jovyan/.code-server/.config/code-server/config.yaml
    done
    touch "${INSTALL_FLAG}"
else
    echo "Drivers previously installed"
fi

# Now fire up VSCode
code-server --bind-addr localhost:$port --auth none \
--user-data-dir /home/jovyan/.code-server \
--config /home/jovyan/.code-server/.config/code-server/config.yaml

