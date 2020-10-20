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

import json
import logging
import os
import shutil
from typing import Any, Dict

from datamaker_cli import DATAMAKER_CLI_ROOT, exceptions, k8s, sh
from datamaker_cli.manifest import Manifest, TeamManifest
from datamaker_cli.remote_files.utils import get_k8s_context
from datamaker_cli.services import cfn

_logger: logging.Logger = logging.getLogger(__name__)


EFS_DRIVE = "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/ecr/?ref=release-1.0"
MODEL_PATH = os.path.join(DATAMAKER_CLI_ROOT, "data", "kubectl")


def _commons(output_path: str) -> None:
    filename = "00-commons.yaml"
    input = os.path.join(MODEL_PATH, filename)
    output = output_path + filename
    shutil.copyfile(src=input, dst=output)


def _team(region: str, account_id: str, output_path: str, env_name: str, team: TeamManifest) -> None:
    input = os.path.join(MODEL_PATH, "01-team.yaml")
    output = output_path + f"01-{team.name}-team.yaml"

    with open(input, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        team=team.name, efsid=team.efs_id, region=region, account_id=account_id, env_name=env_name
    )
    with open(output, "w") as file:
        file.write(content)

    # user service account
    input = os.path.join(MODEL_PATH, "02-user-service-account.yaml")
    output = output_path + f"02-{team.name}-user-service-account.yaml"

    with open(input, "r") as file:
        content = file.read()
    content = content.replace("$", "").format(team=team.name, efsid=team.efs_id, region=region, account_id=account_id)
    with open(output, "w") as file:
        file.write(content)


def _landing_page(
    region: str,
    account_id: str,
    output_path: str,
    env_name: str,
    user_pool_id: str,
    user_pool_client_id: str,
    identity_pool_id: str,
) -> None:
    filename = "03-landing-page.yaml"
    input = os.path.join(MODEL_PATH, filename)
    output = output_path + filename
    with open(input, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        region=region,
        account_id=account_id,
        env_name=env_name,
        user_pool_id=user_pool_id,
        user_pool_client_id=user_pool_client_id,
        identity_pool_id=identity_pool_id,
    )
    with open(output, "w") as file:
        file.write(content)


def _cleanup_output(output_path: str) -> None:
    files = os.listdir(output_path)
    for file in files:
        if file.endswith(".yaml"):
            os.remove(os.path.join(output_path, file))


def _generate_manifest(manifest: Manifest, filename: str) -> str:
    output_path = f"{manifest.filename_dir}.datamaker.out/{manifest.name}/kubectl/"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    _cleanup_output(output_path=output_path)
    _commons(output_path=output_path)

    if manifest.account_id is None:
        raise RuntimeError("manifest.account_id is None!")

    for team in manifest.teams:
        _team(
            region=manifest.region,
            account_id=manifest.account_id,
            env_name=manifest.name,
            output_path=output_path,
            team=team,
        )

    if manifest.user_pool_id is None:
        _logger.warning("manifest.user_pool_id is None, skipping LandingPage Manifest generation.")
        return output_path
    if manifest.user_pool_client_id is None:
        _logger.warning("manifest.user_pool_client_id is None, skipping LandingPage Manifest generation.")
        return output_path
    if manifest.identity_pool_id is None:
        _logger.warning("manifest.identity_pool_id is None, skipping LandingPage Manifest generation.")
        return output_path

    _landing_page(
        region=manifest.region,
        account_id=manifest.account_id,
        output_path=output_path,
        env_name=manifest.name,
        user_pool_id=manifest.user_pool_id,
        user_pool_client_id=manifest.user_pool_client_id,
        identity_pool_id=manifest.identity_pool_id,
    )

    return output_path


def _update_teams_urls(manifest: Manifest, context: str) -> None:
    client = manifest.get_boto3_client(service_name="ssm")
    for team in manifest.teams:
        _logger.debug("Updating team %s URL parameter", team.name)
        url = k8s.get_service_hostname(name="jupyterhub-public", context=context, namespace=team.name)
        json_str: str = client.get_parameter(Name=team.ssm_parameter_name)["Parameter"]["Value"]
        json_obj: Dict[str, Any] = json.loads(json_str)
        json_obj["jupyter-url"] = url
        client.put_parameter(
            Name=team.ssm_parameter_name, Value=json.dumps(json_obj, indent=4, sort_keys=False), Overwrite=True
        )


def _update_landing_page_url(manifest: Manifest, context: str) -> None:
    url: str = k8s.get_service_hostname(name="landing-page-public", context=context, namespace="env")
    url = f"http://{url}"
    manifest.landing_page_url = url
    manifest.write_ssm()


def deploy(manifest: Manifest, filename: str) -> None:
    eks_stack_name: str = f"eksctl-datamaker-{manifest.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=eks_stack_name):
        context = get_k8s_context(manifest=manifest)
        _logger.debug("kubectl context: %s", context)
        output_path = _generate_manifest(manifest=manifest, filename=filename)
        sh.run(f"kubectl apply -k {EFS_DRIVE} --context {context}")
        sh.run(f"kubectl apply -f {output_path} --context {context}")
        _update_teams_urls(manifest=manifest, context=context)
        _update_landing_page_url(manifest=manifest, context=context)


def destroy(manifest: Manifest, filename: str) -> None:
    eks_stack_name: str = f"eksctl-datamaker-{manifest.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
        context = get_k8s_context(manifest=manifest)
        _logger.debug("kubectl context: %s", context)
        output_path = _generate_manifest(manifest=manifest, filename=filename)
        output_path = f"{manifest.filename_dir}.datamaker.out/{manifest.name}/kubectl/"
        try:
            sh.run(f"kubectl delete -f {output_path} --grace-period=0 --force --ignore-not-found --context {context}")
        except exceptions.FailedShellCommand as ex:
            _logger.debug("Skipping: %s", ex)
            pass  # Let's leave for eksctl, it will destroy everything anyway...
