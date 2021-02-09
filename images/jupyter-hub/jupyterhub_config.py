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
from jupyterhub_utils.ssm import ACCOUNT_ID, ENV_NAME, GRANT_SUDO, IMAGE, IMAGE_SPARK, REGION, TEAM, TOOLKIT_S3_BUCKET

PROFILES_TYPE = List[Dict[str, Any]]

app_log.info("ACCOUNT_ID: %s", ACCOUNT_ID)
app_log.info("ENV_NAME: %s", ENV_NAME)
app_log.info("IMAGE: %s", IMAGE)
app_log.info("IMAGE_SPARK: %s", IMAGE_SPARK)
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
c.Spawner.cmd = ["/usr/local/bin/start-singleuser.sh"]
c.Spawner.args = [
    "--SingleUserServerApp.default_url=/lab",
]
c.KubeSpawner.start_timeout = 360
c.KubeSpawner.common_labels = {}
c.KubeSpawner.namespace = TEAM
c.KubeSpawner.environment = {
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
# TODO we want to remove this 'Always' from production code
c.KubeSpawner.image_pull_policy = "Always"
c.KubeSpawner.storage_class = f"ebs-{TEAM}-gp2"
c.KubeSpawner.storage_access_modes = ["ReadWriteOnce"]
c.KubeSpawner.storage_capacity = "5Gi"
c.KubeSpawner.storage_pvc_ensure = True
c.KubeSpawner.extra_annotations = {"AWS_ORBIT_TEAM_SPACE": TEAM, "AWS_ORBIT_ENV": ENV_NAME}
pvc_name_template = "claim-{username}{servername}"
c.KubeSpawner.pvc_name_template = pvc_name_template
c.KubeSpawner.volumes = [
    {"name": "efs-volume", "persistentVolumeClaim": {"claimName": "jupyterhub"}},
    {"name": "ebs-volume", "persistentVolumeClaim": {"claimName": pvc_name_template}},
]
c.KubeSpawner.volume_mounts = [{"mountPath": "/efs", "name": "efs-volume"}, {"mountPath": "/ebs", "name": "ebs-volume"}]
# This will allow Jovyan to write to the ebs volume
c.KubeSpawner.init_containers = [
    {
        "name": "take-ebs-dir-ownership",
        "image": IMAGE,
        "command": ["sh", "-c", "sudo chmod -R 777 /ebs"],
        "securityContext": {"runAsUser": 0},
        "volumeMounts": [{"mountPath": "/ebs", "name": "ebs-volume"}],
    }
]
c.KubeSpawner.fs_gid = 65534
c.KubeSpawner.lifecycle_hooks = {"postStart": {"exec": {"command": ["/bin/sh", "/etc/jupyterhub/bootstrap.sh"]}}}
c.KubeSpawner.node_selector = {"team": TEAM}
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
    {
        "display_name": "Small (Apache Spark)",
        "slug": "small-spark",
        "description": "4 CPU + 8G MEM",
        "kubespawner_override": {
            "image": IMAGE_SPARK,
            "cpu_guarantee": 4,
            "cpu_limit": 4,
            "mem_guarantee": "8G",
            "mem_limit": "8G",
        },
    },
]


def per_user_profiles(spawner):
    team = spawner.environment["AWS_ORBIT_TEAM_SPACE"]
    env = spawner.environment["AWS_ORBIT_ENV"]
    ssm = boto3.Session().client("ssm")
    app_log.info("Getting profiles...")
    ssm_parameter_name: str = f"/orbit/{env}/teams/{team}/manifest"
    json_str: str = ssm.get_parameter(Name=ssm_parameter_name)["Parameter"]["Value"]

    team_manifest_dic = json.loads(json_str)
    if team_manifest_dic.get("profiles"):
        default_profiles = team_manifest_dic["profiles"]
    else:
        app_log.info("No default profiles found")
        default_profiles = profile_list_default

    ssm_parameter_name: str = f"/orbit/{env}/teams/{team}/user/profiles"
    json_str: str = ssm.get_parameter(Name=ssm_parameter_name)["Parameter"]["Value"]

    user_profiles: PROFILES_TYPE = cast(PROFILES_TYPE, json.loads(json_str))
    default_profiles.extend(user_profiles)
    return default_profiles


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
