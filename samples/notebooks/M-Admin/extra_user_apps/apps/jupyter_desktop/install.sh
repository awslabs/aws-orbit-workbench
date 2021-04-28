#!/usr/bin/env bash
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
set -ex
ls -al

apt-get -y update \
 && apt-get install -y dbus-x11 \
   firefox \
   xfce4 \
   xfce4-panel \
   xfce4-session \
   xfce4-settings \
   xorg \
   xubuntu-icon-theme

# Remove light-locker to prevent screen lock
wget 'https://sourceforge.net/projects/turbovnc/files/2.2.5/turbovnc_2.2.5_amd64.deb/download' -O turbovnc_2.2.5_amd64.deb && \
   apt-get install -y -q ./turbovnc_2.2.5_amd64.deb && \
   apt-get remove -y -q light-locker && \
   rm ./turbovnc_2.2.5_amd64.deb && \
   ln -s /opt/TurboVNC/bin/* /usr/local/bin/

conda run pip install -r requirements.txt

curl -o desktop.zip https://codeload.github.com/yuvipanda/jupyter-desktop-server/zip/refs/heads/master
mkdir -p /temp
unzip -o desktop.zip -d /temp
mkdir /opt/install
cp  -R /temp/jupyter-desktop-server-master/* /opt/install
rm -fR /temp/jupyter-desktop-server-master
cd /opt/install
conda env update -n base --file environment.yml

mkdir -p /temp/datagrip
wget -O /temp/datagrip/datagrip-2021.1.tar.gz https://download.jetbrains.com/datagrip/datagrip-2021.1.tar.gz
#curl -o /temp/datagrip/datagrip-2021.1.tar.gz https://download.jetbrains.com/datagrip/datagrip-2021.1.tar.gz
tar xzf /temp/datagrip/datagrip-2021.1.tar.gz -C /temp/datagrip/
mkdir /opt/datagrip
cp -R /temp/datagrip/DataGrip-2021.1/* /opt/datagrip 
rm -rf /temp/datagrip
ln -s /opt/datagrip/bin/datagrip.sh /usr/local/bin/datagrip
