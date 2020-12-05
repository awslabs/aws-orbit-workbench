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
import shutil
from typing import List, Optional

import yaml

from datamaker_cli import DATAMAKER_CLI_ROOT, exceptions, k8s, sh, utils
from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest
from datamaker_cli.remote_files.utils import get_k8s_context
from datamaker_cli.services import cfn

_logger: logging.Logger = logging.getLogger(__name__)


EFS_DRIVE = "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/ecr/?ref=release-1.0"
MODELS_PATH = os.path.join(DATAMAKER_CLI_ROOT, "data", "kubectl")


def _commons(output_path: str) -> None:
    filename = "00-commons.yaml"
    input = os.path.join(MODELS_PATH, "apps", filename)
    output = os.path.join(output_path, filename)
    shutil.copyfile(src=input, dst=output)


def _team(manifest: Manifest, team_manifest: TeamManifest, output_path: str) -> None:
    input = os.path.join(MODELS_PATH, "apps", "01-team.yaml")
    output = os.path.join(output_path, f"01-{team_manifest.name}-team.yaml")

    with open(input, "r") as file:
        content: str = file.read()

    _logger.debug("team.efs_id: %s", team_manifest.efs_id)
    inbound_ranges: List[str] = (
        team_manifest.jupyterhub_inbound_ranges
        if team_manifest.jupyterhub_inbound_ranges
        else [utils.get_dns_ip_cidr(manifest=manifest)]
    )
    content = content.replace("$", "").format(
        team=team_manifest.name,
        efsid=team_manifest.efs_id,
        region=manifest.region,
        account_id=manifest.account_id,
        env_name=manifest.name,
        tag=team_manifest.manifest.images["jupyter-hub"]["version"],
        grant_sudo='"yes"' if team_manifest.grant_sudo else '"no"',
        internal_load_balancer="false" if manifest.load_balancers_subnets else "true",
        jupyterhub_inbound_ranges=inbound_ranges,
    )
    _logger.debug("Kubectl Team %s manifest:\n%s", team_manifest.name, content)
    with open(output, "w") as file:
        file.write(content)

    # user service account
    input = os.path.join(MODELS_PATH, "apps", "02-user-service-account.yaml")
    output = os.path.join(output_path, f"02-{team_manifest.name}-user-service-account.yaml")

    with open(input, "r") as file:
        content = file.read()
    content = content.replace("$", "").format(team=team_manifest.name)
    with open(output, "w") as file:
        file.write(content)


def _landing_page(output_path: str, manifest: Manifest) -> None:
    filename = "03-landing-page.yaml"
    input = os.path.join(MODELS_PATH, "apps", filename)
    output = os.path.join(output_path, filename)

    with open(input, "r") as file:
        content: str = file.read()
    label: Optional[str] = (
        manifest.cognito_external_provider
        if manifest.cognito_external_provider_label is None
        else manifest.cognito_external_provider_label
    )
    domain: str = (
        "null" if manifest.cognito_external_provider_domain is None else manifest.cognito_external_provider_domain
    )
    redirect: str = (
        "null" if manifest.cognito_external_provider_redirect is None else manifest.cognito_external_provider_redirect
    )
    content = content.replace("$", "").format(
        region=manifest.region,
        account_id=manifest.account_id,
        env_name=manifest.name,
        user_pool_id=manifest.user_pool_id,
        user_pool_client_id=manifest.user_pool_client_id,
        identity_pool_id=manifest.identity_pool_id,
        tag=manifest.images["landing-page"]["version"],
        cognito_external_provider=manifest.cognito_external_provider,
        cognito_external_provider_label=label,
        cognito_external_provider_domain=domain,
        cognito_external_provider_redirect=redirect,
        internal_load_balancer="false" if manifest.load_balancers_subnets else "true",
    )
    with open(output, "w") as file:
        file.write(content)


def _cleanup_output(output_path: str) -> None:
    files = os.listdir(output_path)
    for file in files:
        if file.endswith(".yaml"):
            os.remove(os.path.join(output_path, file))


def _generate_env_manifest(manifest: Manifest, clean_up: bool = True) -> str:
    output_path = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, "kubectl", "apps")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)
    _commons(output_path=output_path)

    if manifest.account_id is None:
        raise RuntimeError("manifest.account_id is None!")

    if manifest.user_pool_id is None:
        _logger.warning("manifest.user_pool_id is None, skipping LandingPage Manifest generation.")
        return output_path
    if manifest.user_pool_client_id is None:
        _logger.warning("manifest.user_pool_client_id is None, skipping LandingPage Manifest generation.")
        return output_path
    if manifest.identity_pool_id is None:
        _logger.warning("manifest.identity_pool_id is None, skipping LandingPage Manifest generation.")
        return output_path

    _landing_page(output_path=output_path, manifest=manifest)

    return output_path


def _generate_teams_manifest(manifest: Manifest) -> str:
    output_path = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, "kubectl", "apps")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    if manifest.account_id is None:
        raise RuntimeError("manifest.account_id is None!")

    for team_manifest in manifest.teams:
        _team(manifest=manifest, team_manifest=team_manifest, output_path=output_path)

    return output_path


def _generate_aws_auth_config_map(manifest: Manifest, context: str, with_teams: bool) -> str:
    output_path = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, "kubectl", "aws_auth_config_map")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    config_map = yaml.load(
        "\n".join(sh.run_iterating(f"kubectl get configmap --context {context} -o yaml -n kube-system aws-auth")),
        Loader=yaml.SafeLoader,
    )
    map_roles = yaml.load(config_map["data"]["mapRoles"], Loader=yaml.SafeLoader)
    team_usernames = {f"datamaker-{manifest.name}-{t.name}" for t in manifest.teams}

    map_roles = [role for role in map_roles if role["username"] not in team_usernames]

    if with_teams:
        for username in team_usernames:
            map_roles.append(
                {
                    "groups": ["system:masters"],
                    "rolearn": f"arn:aws:iam::{manifest.account_id}:role/{username}-role",
                    "username": username,
                }
            )

    config_map["data"]["mapRoles"] = yaml.dump(map_roles)
    config_map_file = os.path.join(output_path, "config_map.yaml")
    _logger.debug(f"config_map: {config_map}")
    _logger.debug(f"config_map_yaml: {config_map_file}")
    with open(config_map_file, "w") as yaml_file:
        yaml_file.write(yaml.dump(config_map))

    return config_map_file


def fetch_kubectl_data(manifest: Manifest, context: str, include_teams: bool) -> None:
    _logger.debug("Fetching Kubectl data...")
    manifest.fetch_ssm()

    if include_teams:
        for team in manifest.teams:
            _logger.debug("Fetching team %s URL parameter", team.name)
            url = k8s.get_service_hostname(name="jupyterhub-public", context=context, namespace=team.name)
            team.jupyter_url = url
            team.write_manifest_ssm()

    landing_page_url: str = k8s.get_service_hostname(name="landing-page-public", context=context, namespace="env")
    manifest.landing_page_url = f"http://{landing_page_url}"

    manifest.write_manifest_ssm()
    _logger.debug("Kubectl data fetched successfully.")


def _efs_driver_base(output_path: str) -> None:
    os.makedirs(os.path.join(output_path, "base"), exist_ok=True)
    filenames = ("csidriver.yaml", "kustomization.yaml", "node.yaml")
    for filename in filenames:
        input = os.path.join(MODELS_PATH, "efs_driver", "base", filename)
        output = os.path.join(output_path, "base", filename)
        _logger.debug("Copying efs driver base file: %s -> %s", input, output)
        shutil.copyfile(src=input, dst=output)


def _efs_driver_overlays(output_path: str, manifest: Manifest) -> None:
    filename = "kustomization.yaml"
    input = os.path.join(MODELS_PATH, "efs_driver", "overlays", filename)
    os.makedirs(os.path.join(output_path, "overlays"), exist_ok=True)
    output = os.path.join(output_path, "overlays", filename)
    with open(input, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        region=manifest.region,
        account_id=manifest.account_id,
        env_name=manifest.name,
    )
    with open(output, "w") as file:
        file.write(content)


def _generate_efs_driver_manifest(manifest: Manifest) -> str:
    output_path = os.path.join(manifest.filename_dir, ".datamaker.out", manifest.name, "kubectl", "efs_driver")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    if manifest.account_id is None:
        raise RuntimeError("manifest.account_id is None!")
    if manifest.region is None:
        raise RuntimeError("manifest.region is None!")
    _efs_driver_base(output_path=output_path)
    _efs_driver_overlays(output_path=output_path, manifest=manifest)
    return os.path.join(output_path, "overlays")


def deploy_env(manifest: Manifest) -> None:
    eks_stack_name: str = f"eksctl-datamaker-{manifest.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=eks_stack_name):
        context = get_k8s_context(manifest=manifest)
        _logger.debug("kubectl context: %s", context)
        if manifest.internet_accessible is False:
            output_path = _generate_efs_driver_manifest(manifest=manifest)
            sh.run(f"kubectl apply -k {output_path} --context {context}")
        else:
            sh.run(f"kubectl apply -k {EFS_DRIVE} --context {context}")
        output_path = _generate_env_manifest(manifest=manifest)
        sh.run(f"kubectl apply -f {output_path} --context {context}")
        fetch_kubectl_data(manifest=manifest, context=context, include_teams=False)


def deploy_teams(manifest: Manifest) -> None:
    eks_stack_name: str = f"eksctl-datamaker-{manifest.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=eks_stack_name):
        context = get_k8s_context(manifest=manifest)
        _logger.debug("kubectl context: %s", context)
        output_path = _generate_teams_manifest(manifest=manifest)
        output_path = _generate_env_manifest(manifest=manifest, clean_up=False)
        sh.run(f"kubectl apply -f {output_path} --context {context}")
        output_path = _generate_aws_auth_config_map(manifest=manifest, context=context, with_teams=True)
        _logger.debug("Updating aws-auth configMap")
        sh.run(f"kubectl apply -f {output_path} --context {context}")
        fetch_kubectl_data(manifest=manifest, context=context, include_teams=True)


def destroy_env(manifest: Manifest) -> None:
    eks_stack_name: str = f"eksctl-datamaker-{manifest.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
        context = get_k8s_context(manifest=manifest)
        _logger.debug("kubectl context: %s", context)
        output_path = _generate_env_manifest(manifest=manifest)
        try:
            sh.run(
                f"kubectl delete -f {output_path} --grace-period=0 --force "
                f"--ignore-not-found --wait --context {context}"
            )
        except exceptions.FailedShellCommand as ex:
            _logger.debug("Skipping: %s", ex)
            pass  # Let's leave for eksctl, it will destroy everything anyway...


def destroy_teams(manifest: Manifest) -> None:
    eks_stack_name: str = f"eksctl-datamaker-{manifest.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(manifest=manifest, stack_name=eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster datamaker-{manifest.name} --set-kubeconfig-context")
        context = get_k8s_context(manifest=manifest)
        _logger.debug("kubectl context: %s", context)
        output_path = _generate_aws_auth_config_map(manifest=manifest, context=context, with_teams=False)
        _logger.debug("Updating aws-auth configMap")
        sh.run(f"kubectl apply -f {output_path} --context {context}")
        _logger.debug("Attempting kubectl delete")
        output_path = _generate_teams_manifest(manifest=manifest)
        try:
            sh.run(
                f"kubectl delete -f {output_path} --grace-period=0 --force "
                f"--ignore-not-found --wait --context {context}"
            )
        except exceptions.FailedShellCommand as ex:
            _logger.debug("Skipping: %s", ex)
            pass  # Let's leave for eksctl, it will destroy everything anyway...
