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

import concurrent.futures
import json
import logging
from concurrent.futures import Future
from typing import Any, Dict, List, cast

import boto3
import click
from kubernetes import config
from kubernetes.client import CoreV1Api, V1Service

from datamaker_cli import cdk, demo, eksctl, jupyter_hub, jupyter_user, kubectl, landing_page
from datamaker_cli.manifest import Manifest, read_manifest_file
from datamaker_cli.spinner import start_spinner
from datamaker_cli.utils import does_cfn_exist, get_k8s_context, stylize

_logger: logging.Logger = logging.getLogger(__name__)


def _fetch_users_url(manifest: Manifest) -> None:
    url: str = (
        f"https://{manifest.region}.console.aws.amazon.com/cognito/users/?"
        f"region={manifest.region}#/pool/{manifest.user_pool_id}/users"
    )
    click.echo(message=(f"\n{stylize('User Pool URL:')} {url}"))


def _get_service_hostname(name: str, context: str, namespace: str = "default") -> str:
    config.load_kube_config(context=context)
    v1 = CoreV1Api()
    while True:
        resp = cast(V1Service, v1.read_namespaced_service_status(name=name, namespace=namespace))
        status: Dict[str, Any] = resp.status.to_dict()
        if "load_balancer" in status:
            if "ingress" in status["load_balancer"]:
                if status["load_balancer"]["ingress"]:
                    if "hostname" in status["load_balancer"]["ingress"][0]:
                        break
    return str(status["load_balancer"]["ingress"][0]["hostname"])


def _fetch_landing_page_url(context: str) -> None:
    url: str = _get_service_hostname(name="landing-page-public", context=context, namespace="env")
    click.echo(message=(f"{stylize('DataMaker URL:')} http://{url}\n"))


def _update_teams_urls(manifest: Manifest, context: str) -> None:
    client = boto3.client(service_name="ssm")
    for team in manifest.teams:
        url = _get_service_hostname(name="jupyterhub-public", context=context, namespace=team.name)
        json_str: str = client.get_parameter(Name=team.ssm_parameter_name)["Parameter"]["Value"]
        json_obj: Dict[str, Any] = json.loads(json_str)
        json_obj["jupyter-url"] = url
        client.put_parameter(
            Name=team.ssm_parameter_name, Value=json.dumps(json_obj, indent=4, sort_keys=False), Overwrite=True
        )


def deploy(filename: str) -> None:
    manifest: Manifest = read_manifest_file(filename=filename)
    if manifest.demo:
        manifest = demo.deploy(manifest=manifest, filename=filename)
    manifest = cdk.deploy(manifest=manifest, filename=filename)

    cdk_stack_name: str = f"datamaker-{manifest.name}"
    if does_cfn_exist(stack_name=cdk_stack_name):
        with start_spinner(msg="Deploying the EKS cluster and all related Docker images concurrently") as spinner:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures: List[Future[Any]] = []
                futures.append(executor.submit(eksctl.deploy, manifest, filename))
                futures.append(executor.submit(jupyter_hub.deploy, manifest))
                futures.append(executor.submit(jupyter_user.deploy, manifest))
                futures.append(executor.submit(landing_page.deploy, manifest))
                for f in futures:
                    f.result()
            spinner.succeed()

        context = get_k8s_context(manifest=manifest)
        _logger.debug("kubectl context: %s", context)

        manifest = kubectl.deploy(manifest=manifest, filename=filename, context=context)

        _update_teams_urls(manifest=manifest, context=context)
        _fetch_users_url(manifest=manifest)
        _fetch_landing_page_url(context=context)
