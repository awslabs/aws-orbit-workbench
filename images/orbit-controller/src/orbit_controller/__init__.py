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

import logging
import os
import subprocess

from kubernetes import config as k8_config
from kubernetes import dynamic
from kubernetes.client import api_client

ORBIT_API_VERSION = os.environ.get("ORBIT_API_VERSION", "v1")
ORBIT_API_GROUP = os.environ.get("ORBIT_API_GROUP", "orbit.aws")
ORBIT_SYSTEM_NAMESPACE = os.environ.get("ORBIT_SYSTEM_NAMESPACE", "orbit-system")
ORBIT_STATE_PATH = os.environ.get("ORBIT_STATE_PATH", "/state")

DEBUG_LOGGING_FORMAT = "[%(asctime)s][%(filename)-13s:%(lineno)3d][%(levelname)s][%(threadName)s] %(message)s"


def _get_logger() -> logging.Logger:
    debug = os.environ.get("ORBIT_CONTROLLER_DEBUG", "False").lower() in [
        "true",
        "yes",
        "1",
    ]
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format=DEBUG_LOGGING_FORMAT)
    logger: logging.Logger = logging.getLogger(__name__)
    logger.setLevel(level)
    if debug:
        logging.getLogger("boto3").setLevel(logging.ERROR)
        logging.getLogger("botocore").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.ERROR)
        logging.getLogger("kubernetes").setLevel(logging.ERROR)
    return logger


def load_config(in_cluster: bool = True) -> None:
    in_cluster_env = os.environ.get("IN_CLUSTER_DEPLOYMENT", None)
    in_cluster = in_cluster_env.lower() in ["yes", "true", "1"] if in_cluster_env is not None else in_cluster
    if in_cluster:
        logger.debug("Loading In-Cluster Config")
        k8_config.load_incluster_config()
    else:
        logger.debug("Loading Off-Cluster Config")
        k8_config.load_kube_config()


def run_command(cmd: str) -> str:
    """ Module to run shell commands. """
    try:
        output = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            shell=True,
            timeout=29,
            universal_newlines=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.debug("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output))
        raise Exception(exc.output)
    return output


def dynamic_client() -> dynamic.DynamicClient:
    load_config()
    return dynamic.DynamicClient(client=api_client.ApiClient())


logger = _get_logger()
