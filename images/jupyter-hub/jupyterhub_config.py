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

import os

from tornado.log import app_log

from jupyterhub_utils.authenticator import DataMakerAuthenticator
from jupyterhub_utils.ssm import ACCOUNT_ID, ENV_NAME, IMAGE, REGION, TEAM, TOOLKIT_S3_BUCKET

app_log.info("ACCOUNT_ID: %s", ACCOUNT_ID)
app_log.info("ENV_NAME: %s", ENV_NAME)
app_log.info("IMAGE: %s", IMAGE)
app_log.info("REGION: %s", REGION)
app_log.info("TEAM: %s", TEAM)
app_log.info("TOOLKIT_S3_BUCKET: %s", TOOLKIT_S3_BUCKET)

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
c.KubeSpawner.start_timeout = 360
c.KubeSpawner.common_labels = {}
c.KubeSpawner.namespace = TEAM
c.KubeSpawner.environment = {
    "USERNAME": lambda spawner: str(spawner.user.name),
    "JUPYTER_ENABLE_LAB": "true",
    "DATAMAKER_TEAM_SPACE": TEAM,
    "AWS_DATAMAKER_ENV": ENV_NAME,
    "AWS_DEFAULT_REGION": REGION,
    "ACCOUNT_ID": ACCOUNT_ID,
    "AWS_DATAMAKER_S3_BUCKET": TOOLKIT_S3_BUCKET,
}
c.KubeSpawner.image = IMAGE
c.KubeSpawner.image_pull_policy = "Always"
c.KubeSpawner.volumes = [{"name": "efs-volume", "persistentVolumeClaim": {"claimName": "jupyterhub"}}]
c.KubeSpawner.volume_mounts = [{"mountPath": "/efs", "name": "efs-volume"}]
c.KubeSpawner.lifecycle_hooks = {
    "postStart": {"exec": {"command": ["/bin/sh", "/etc/jupyterhub/link-user-efs-directory.sh"]}}
}
c.KubeSpawner.node_selector = {"team": TEAM}
c.KubeSpawner.service_account = "jupyter-user"
c.KubeSpawner.profile_list = [
    {
        "display_name": "Nano",
        "slug": "nano",
        "description": "1 CPU + 1G MEM",
        "kubespawner_override": {
            "cpu_guarantee": 1,
            "cpu_limit": 1,
            "mem_guarantee": "1G",
            "mem_limit": "1G",
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
]

"""
AUTH
"""

c.JupyterHub.authenticator_class = DataMakerAuthenticator
c.Authenticator.auto_login = True

"""
EXTRAS
"""

c.JupyterHub.shutdown_on_logout = True
c.JupyterHub.tornado_settings = {"slow_spawn_timeout": 360}
