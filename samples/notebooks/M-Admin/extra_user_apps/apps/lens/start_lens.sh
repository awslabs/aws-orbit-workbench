#!/bin/bash

sudo chmod +x /opt/orbit/codeserver_proxy/create_kubeconfig.sh
source /opt/orbit/codeserver_proxy/create_kubeconfig.sh

sudo chmod a+x /opt/orbit/extra_use_apps/apps/lens/Lens-5.1.3.AppImage
./Lens-5.1.3.AppImage --appimage-extract-and-run