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
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from aws_orbit import ORBIT_CLI_ROOT, exceptions, k8s, plugins, sh, utils
from aws_orbit.models.context import dump_context_to_ssm
from aws_orbit.remote_files.utils import get_k8s_context
from aws_orbit.services import cfn, elb

if TYPE_CHECKING:
    from aws_orbit.models.changeset import PluginChangeset
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger(__name__)


EFS_DRIVE = "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/ecr/?ref=release-1.0"
MODELS_PATH = os.path.join(ORBIT_CLI_ROOT, "data", "kubectl")


def _commons(context: "Context", output_path: str) -> None:
    filename = "00-commons.yaml"
    input = os.path.join(MODELS_PATH, "apps", filename)
    output = os.path.join(output_path, filename)

    with open(input, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        region=context.region,
        env_name=context.name,
    )
    with open(output, "w") as file:
        file.write(content)


def _team(context: "Context", team_context: "TeamContext", output_path: str) -> None:
    input = os.path.join(MODELS_PATH, "apps", "01-team.yaml")
    output = os.path.join(output_path, f"01-{team_context.name}-team.yaml")

    with open(input, "r") as file:
        content: str = file.read()

    inbound_ranges: List[str] = (
        team_context.jupyterhub_inbound_ranges
        if team_context.jupyterhub_inbound_ranges
        else [utils.get_dns_ip_cidr(context=context)]
    )
    content = content.replace("$", "").format(
        team=team_context.name,
        efsid=context.shared_efs_fs_id,
        efsapid=team_context.efs_ap_id,
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        tag=context.images.jupyter_hub.version,
        grant_sudo='"yes"' if team_context.grant_sudo else '"no"',
        internal_load_balancer='"false"' if context.networking.frontend.load_balancers_subnets else '"true"',
        jupyterhub_inbound_ranges=inbound_ranges,
        team_kms_key_arn=team_context.team_kms_key_arn,
    )
    _logger.debug("Kubectl Team %s manifest:\n%s", team_context.name, content)
    with open(output, "w") as file:
        file.write(content)

    # user service account
    input = os.path.join(MODELS_PATH, "apps", "02-user-service-account.yaml")
    output = os.path.join(output_path, f"02-{team_context.name}-user-service-account.yaml")

    with open(input, "r") as file:
        content = file.read()
    content = content.replace("$", "").format(team=team_context.name)
    with open(output, "w") as file:
        file.write(content)


def _landing_page(output_path: str, context: "Context") -> None:
    filename = "03-landing-page.yaml"
    input = os.path.join(MODELS_PATH, "apps", filename)
    output = os.path.join(output_path, filename)

    with open(input, "r") as file:
        content: str = file.read()
    label: Optional[str] = (
        context.cognito_external_provider
        if context.cognito_external_provider_label is None
        else context.cognito_external_provider_label
    )
    domain: str = (
        "null" if context.cognito_external_provider_domain is None else context.cognito_external_provider_domain
    )
    redirect: str = (
        "null" if context.cognito_external_provider_redirect is None else context.cognito_external_provider_redirect
    )
    content = content.replace("$", "").format(
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
        user_pool_id=context.user_pool_id,
        user_pool_client_id=context.user_pool_client_id,
        identity_pool_id=context.identity_pool_id,
        tag=context.images.landing_page.version,
        cognito_external_provider=context.cognito_external_provider,
        cognito_external_provider_label=label,
        cognito_external_provider_domain=domain,
        cognito_external_provider_redirect=redirect,
        internal_load_balancer='"false"' if context.networking.frontend.load_balancers_subnets else '"true"',
    )
    with open(output, "w") as file:
        file.write(content)


def _cleanup_output(output_path: str) -> None:
    files = os.listdir(output_path)
    for file in files:
        if file.endswith(".yaml"):
            os.remove(os.path.join(output_path, file))


def _generate_env_manifest(context: "Context", clean_up: bool = True) -> str:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "apps")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)
    _commons(context=context, output_path=output_path)

    if context.account_id is None:
        raise ValueError("context.account_id is None!")
    if context.user_pool_id is None:
        raise ValueError("context.user_pool_id is None!")
    if context.user_pool_client_id is None:
        raise ValueError("context.user_pool_client_id is None!")
    if context.identity_pool_id is None:
        raise ValueError("context.identity_pool_id is None!")

    _landing_page(output_path=output_path, context=context)

    return output_path


def _prepare_team_context_path(context: "Context") -> str:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "apps")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    if context.account_id is None:
        raise RuntimeError("context.account_id is None!")
    return output_path


def _generate_teams_manifest(context: "Context") -> str:
    output_path: str = _prepare_team_context_path(context=context)
    for team_context in context.teams:
        _team(context=context, team_context=team_context, output_path=output_path)
    return output_path


def _generate_team_context(context: "Context", team_context: "TeamContext") -> str:
    output_path: str = _prepare_team_context_path(context=context)
    _team(context=context, team_context=team_context, output_path=output_path)
    return output_path


def _update_elbs(context: "Context") -> None:
    elbs: Dict[str, Dict[str, Any]] = elb.get_elbs_by_service(env_name=context.name)
    # Env ELBs
    context.elbs = {k: v for k, v in elbs.items() if k.startswith("env/")}
    # Teams ELBS
    for team in context.teams:
        team.elbs = {k: v for k, v in elbs.items() if k.startswith(f"{team.name}/")}


def fetch_kubectl_data(context: "Context", k8s_context: str, include_teams: bool) -> None:
    _logger.debug("Fetching Kubectl data...")

    if include_teams:
        for team in context.teams:
            _logger.debug("Fetching team %s URL parameter", team.name)
            url = k8s.get_service_hostname(name="jupyterhub-public", k8s_context=k8s_context, namespace=team.name)
            team.jupyter_url = url

    landing_page_url: str = k8s.get_service_hostname(
        name="landing-page-public", k8s_context=k8s_context, namespace="env"
    )
    context.landing_page_url = f"http://{landing_page_url}"
    _update_elbs(context=context)

    dump_context_to_ssm(context=context)
    _logger.debug("Kubectl data fetched successfully.")


def _efs_driver_base(output_path: str) -> None:
    os.makedirs(os.path.join(output_path, "base"), exist_ok=True)
    filenames = ("csidriver.yaml", "kustomization.yaml", "node.yaml")
    for filename in filenames:
        input = os.path.join(MODELS_PATH, "efs_driver", "base", filename)
        output = os.path.join(output_path, "base", filename)
        _logger.debug("Copying efs driver base file: %s -> %s", input, output)
        shutil.copyfile(src=input, dst=output)


def _efs_driver_overlays(output_path: str, context: "Context") -> None:
    filename = "kustomization.yaml"
    input = os.path.join(MODELS_PATH, "efs_driver", "overlays", filename)
    os.makedirs(os.path.join(output_path, "overlays"), exist_ok=True)
    output = os.path.join(output_path, "overlays", filename)
    with open(input, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        region=context.region,
        account_id=context.account_id,
        env_name=context.name,
    )
    with open(output, "w") as file:
        file.write(content)


def _generate_efs_driver_manifest(context: "Context") -> str:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "efs_driver")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    if context.account_id is None:
        raise RuntimeError("context.account_id is None!")
    if context.region is None:
        raise RuntimeError("context.region is None!")
    _efs_driver_base(output_path=output_path)
    _efs_driver_overlays(output_path=output_path, context=context)
    return os.path.join(output_path, "overlays")


def deploy_env(context: "Context") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        k8s_context = get_k8s_context(context=context)
        _logger.debug("k8s_context: %s", k8s_context)
        if context.networking.data.internet_accessible is False:
            output_path = _generate_efs_driver_manifest(context=context)
            sh.run(f"kubectl apply -k {output_path} --context {k8s_context} --wait")
        else:
            sh.run(f"kubectl apply -k {EFS_DRIVE} --context {k8s_context} --wait")
        output_path = _generate_env_manifest(context=context)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")
        fetch_kubectl_data(context=context, k8s_context=k8s_context, include_teams=False)


def deploy_teams(context: "Context", changes: List["PluginChangeset"]) -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl context: %s", k8s_context)
        output_path = _generate_teams_manifest(context=context)
        output_path = _generate_env_manifest(context=context, clean_up=False)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")
        fetch_kubectl_data(context=context, k8s_context=k8s_context, include_teams=True)
        for team_context in context.teams:
            plugins.PLUGINS_REGISTRIES.deploy_team_plugins(context=context, team_context=team_context, changes=changes)


def destroy_env(context: "Context") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl k8s_context: %s", k8s_context)
        output_path = _generate_env_manifest(context=context)
        try:
            sh.run(
                f"kubectl delete -f {output_path} --grace-period=0 --force "
                f"--ignore-not-found --wait --context {k8s_context}"
            )
        except exceptions.FailedShellCommand as ex:
            _logger.debug("Skipping: %s", ex)
            pass  # Let's leave for eksctl, it will destroy everything anyway...


def destroy_teams(context: "Context") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        for team_context in context.teams:
            plugins.PLUGINS_REGISTRIES.destroy_team_plugins(context=context, team_context=team_context)
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl k8s_context: %s", k8s_context)
        _logger.debug("Attempting kubectl delete")
        output_path = _generate_teams_manifest(context=context)
        try:
            sh.run(
                f"kubectl delete -f {output_path} --grace-period=0 --force "
                f"--ignore-not-found --wait=false --context {k8s_context}"
            )
        except exceptions.FailedShellCommand as ex:
            _logger.debug("Skipping: %s", ex)
            pass  # Let's leave for eksctl, it will destroy everything anyway...


def destroy_team(context: "Context", team_context: "TeamContext") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl k8s_context: %s", k8s_context)
        _logger.debug("Attempting kubectl delete for team %s", team_context.name)
        output_path = _generate_team_context(context=context, team_context=team_context)
        sh.run(
            f"kubectl delete -f {output_path} --grace-period=0 --force "
            f"--ignore-not-found --wait --context {k8s_context}"
        )
