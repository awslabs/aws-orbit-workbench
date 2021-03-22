#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

# type: ignore

import json
import os
import sys
from typing import Any, Dict, List, cast

import boto3
from tornado.log import app_log

from jupyterhub_utils.authenticator import OrbitWorkbenchAuthenticator
from jupyterhub_utils.ssm import ACCOUNT_ID, ENV_NAME, GRANT_SUDO, IMAGE, REGION, TEAM, TOOLKIT_S3_BUCKET

PROFILES_TYPE = List[Dict[str, Any]]

app_log.info("ACCOUNT_ID: %s", ACCOUNT_ID)
app_log.info("ENV_NAME: %s", ENV_NAME)
app_log.info("IMAGE: %s", IMAGE)
app_log.info("REGION: %s", REGION)
app_log.info("TEAM: %s", TEAM)
app_log.info("TOOLKIT_S3_BUCKET: %s", TOOLKIT_S3_BUCKET)
app_log.info("GRANT_SUDO: %s", GRANT_SUDO)

"""
CONNECTIVITY
"""

c.JupyterHub.hub_connect_ip = os.environ["JUPYTERHUB_PRIVATE_SERVICE_HOST"]
c.JupyterHub.hub_connect_port = int(os.environ["JUPYTERHUB_PRIVATE_SERVICE_PORT"])
c.JupyterHub.hub_ip = "0.0.0.0"

"""
SPAWNER
"""

c.JupyterHub.spawner_class = "kubespawner.KubeSpawner"
c.Spawner.default_url = "/lab"
c.Spawner.cmd = ["/usr/local/bin/start-singleuser.sh", "-e", "CHOWN_EXTRA=/home/jovyan/.aws/cache"]
c.Spawner.args = [
    "--SingleUserServerApp.default_url=/lab",
]
c.KubeSpawner.start_timeout = 600
c.KubeSpawner.common_labels = {"orbit/node-type": "ec2", "orbit/attach-security-group": "yes"}
c.KubeSpawner.namespace = TEAM
c.KubeSpawner.environment = {
    "JUPYTERHUB_SINGLEUSER_APP": "jupyter_server.serverapp.ServerApp",
    "USERNAME": lambda spawner: str(spawner.user.name),
    "JUPYTER_ENABLE_LAB": "yes",
    "AWS_ORBIT_TEAM_SPACE": TEAM,
    "AWS_ORBIT_ENV": ENV_NAME,
    "AWS_DEFAULT_REGION": REGION,
    "ACCOUNT_ID": ACCOUNT_ID,
    "AWS_ORBIT_S3_BUCKET": TOOLKIT_S3_BUCKET,
    "GRANT_SUDO": GRANT_SUDO,
    "AWS_STS_REGIONAL_ENDPOINTS": "regional",
}
if GRANT_SUDO == "yes":
    c.KubeSpawner.uid = 0

c.KubeSpawner.image = IMAGE
# can below if need to force image pull
# c.KubeSpawner.image_pull_policy = "Always"
c.KubeSpawner.extra_annotations = {"AWS_ORBIT_TEAM_SPACE": TEAM, "AWS_ORBIT_ENV": ENV_NAME}
pvc_name_template = "orbit-{username}-{servername}"
c.KubeSpawner.pvc_name_template = pvc_name_template
c.KubeSpawner.volumes = [{"name": "efs-volume", "persistentVolumeClaim": {"claimName": "jupyterhub"}}]
c.KubeSpawner.volume_mounts = [{"mountPath": "/efs", "name": "efs-volume"}]
c.KubeSpawner.fs_gid = 100
c.KubeSpawner.lifecycle_hooks = {"postStart": {"exec": {"command": ["/bin/sh", "/home/jovyan/.orbit/bootstrap.sh"]}}}
c.KubeSpawner.node_selector = {"orbit/usage": "teams", "orbit/node-type": "ec2"}
c.KubeSpawner.service_account = f"{TEAM}"
c.JupyterHub.allow_named_servers = True
c.JupyterHub.named_server_limit_per_user = 5
c.JupyterHub.services = [
    {
        "name": "idle-culler",
        "admin": True,
        "command": [sys.executable, "-m", "jupyterhub_idle_culler", "--remove-named-servers=True", "--timeout=28800"],
    }
]
profile_list_default = [
    {
        "display_name": "Nano",
        "slug": "nano",
        "description": "1 CPU + 1G MEM",
        "kubespawner_override": {
            "cpu_guarantee": 1,
            "cpu_limit": 1,
            "mem_guarantee": "1G",
            "mem_limit": "1G",
            "storage_capacity": "2Gi",
        },
    },
    {
        "display_name": "Micro",
        "slug": "micro",
        "description": "2 CPU + 2G MEM",
        "kubespawner_override": {
            "cpu_guarantee": 2,
            "cpu_limit": 2,
            "mem_guarantee": "2G",
            "mem_limit": "2G",
        },
        "default": True,
    },
    {
        "display_name": "Small",
        "slug": "small",
        "description": "4 CPU + 8G MEM",
        "kubespawner_override": {
            "cpu_guarantee": 4,
            "cpu_limit": 4,
            "mem_guarantee": "8G",
            "mem_limit": "8G",
        },
    },
]

# reset the profile list so its loaded every time from SSM
def userdata_hook(spawner, auth_state):
    spawner._profile_list = None


c.Spawner.auth_state_hook = userdata_hook


def per_user_profiles(spawner):
    ssm = boto3.Session().client("ssm")
    app_log.info("Getting profiles...")
    ssm_parameter_name: str = f"/orbit/{ENV_NAME}/teams/{TEAM}/context"
    json_str: str = ssm.get_parameter(Name=ssm_parameter_name)["Parameter"]["Value"]
    profiles = []
    team_manifest_dic = json.loads(json_str)
    if team_manifest_dic.get("Profiles"):
        profiles.extend(team_manifest_dic["Profiles"])
    else:
        app_log.info("No default profiles found")
        profiles.extend(profile_list_default)

    ssm_parameter_name: str = f"/orbit/{ENV_NAME}/teams/{TEAM}/user/profiles"
    json_str: str = ssm.get_parameter(Name=ssm_parameter_name)["Parameter"]["Value"]

    user_profiles: PROFILES_TYPE = cast(PROFILES_TYPE, json.loads(json_str))
    profiles.extend(user_profiles)
    return profiles


c.KubeSpawner.profile_list = per_user_profiles

"""
AUTH
"""

c.JupyterHub.authenticator_class = OrbitWorkbenchAuthenticator
c.Authenticator.auto_login = True

"""
EXTRAS
"""

c.JupyterHub.shutdown_on_logout = True
c.JupyterHub.tornado_settings = {"slow_spawn_timeout": 360}
