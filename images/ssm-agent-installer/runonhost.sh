#!/bin/bash
# Inspired by https://medium.com/@patnaikshekhar/initialize-your-aks-nodes-with-daemonsets-679fa81fd20e

# Copy installation script to host
cp /tmp/install.sh /host

# Copy rpm to host
cp /rpmtmp/amazon-ssm-agent.rpm /host

# Copy wait script to the host
cp /wait.sh /host

# Wait for updates to complete
/usr/bin/nsenter -m/proc/1/ns/mnt -- chmod u+x /tmp/install/wait.sh

# Give execute priv to script
/usr/bin/nsenter -m/proc/1/ns/mnt -- chmod u+x /tmp/install/install.sh

# Wait for Node updates to complete
/usr/bin/nsenter -m/proc/1/ns/mnt /tmp/install/wait.sh

# If the /tmp folder is mounted on the host then it can run the script
/usr/bin/nsenter -m/proc/1/ns/mnt /tmp/install/install.sh

# Sleep 30 seconds, then exit
echo "Waiting for 30 seconds..."
sleep 30
echo "Task Completed"