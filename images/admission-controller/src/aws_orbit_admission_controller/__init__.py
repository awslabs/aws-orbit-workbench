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
import subprocess
from typing import Optional

from kubernetes import config as k8_config


def load_config(in_cluster: bool = True) -> None:
    if in_cluster:
        k8_config.load_incluster_config()
    else:
        k8_config.load_kube_config()


def run_command(logger: logging.Logger, cmd: str) -> str:
    """ Module to run shell commands. """
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, timeout=3, universal_newlines=True)
    except subprocess.CalledProcessError as exc:
        logger.debug("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output.decode("utf-8")))
        raise Exception(exc.output.decode("utf-8"))
    return output


def install_chart(logger: logging.Logger, repo: str, namespace: str, name: str, chart_name: str,
                  chart_version: Optional[str]) -> str:
    logger.debug("Installing %s, version %s as %s from %s", chart_name, chart_version, name, repo)
    try:
        if chart_version:
            version = f'--version {chart_version}'
        else:
            version = ''

        output = subprocess.check_output(
            f"helm upgrade --install --debug --namespace {namespace} {version} "
            f"{chart_version} {name} {repo}/{chart_name}"
        )
    except subprocess.CalledProcessError as exc:
        logger.debug("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output.decode("utf-8")))
        raise Exception(exc.output.decode("utf-8"))

    return output
