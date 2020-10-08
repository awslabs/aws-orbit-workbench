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

import os
from typing import Any, Dict, Optional

from datamaker._kubernetes import _cron_job
from kubernetes import config
from kubernetes.client import BatchV1beta1Api

TEAM = os.environ.get("TEAM", "NO_TEAM_CONFIGURED")


def schedule_notebook(path: str, schedule: str, timeout: int = 600, env_vars: Optional[Dict[str, Any]] = None) -> None:
    env_vars = {} if env_vars is None else env_vars
    name: str = path.replace("/", "-").replace("_", "-").rsplit(".")[0]
    cmd = f"python /etc/jupyterhub/execute-notebook.py {path} {timeout}"
    config.load_incluster_config()
    BatchV1beta1Api().create_namespaced_cron_job(
        namespace=TEAM,
        body=_cron_job(namespace=TEAM, name=name, cmds=cmd.split(" "), schedule=schedule, env_vars=env_vars),
    )
