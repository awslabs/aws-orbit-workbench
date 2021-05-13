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
from typing import Any, Dict, Optional, Tuple, cast

import yaml

import aws_orbit
from aws_orbit import ORBIT_CLI_ROOT, exceptions, sh, utils
from aws_orbit.models.context import Context, ContextSerDe, TeamContext
from aws_orbit.remote_files import kubectl
from aws_orbit.services import cfn, s3

_logger: logging.Logger = logging.getLogger(__name__)


CHARTS_PATH = os.path.join(ORBIT_CLI_ROOT, "data", "charts")


def update_file(file_path: str, values: Dict[str, Any]) -> str:
    with open(file_path, "r") as file:
        _logger.debug("Updating file %s with values: %s", file_path, values)
        content: str = file.read()
    content = utils.resolve_parameters(content, values)
    with open(file_path, "w") as file:
        file.write(content)
    return content


def create_team_charts_copy(team_context: TeamContext, path: str) -> str:
    dirs = path.split("/")
    charts_dir = dirs.pop()
    charts_path = "/".join(dirs)
    team_charts_path = os.path.join(charts_path, ".output", team_context.name)
    os.makedirs(team_charts_path, exist_ok=True)
    return str(
        shutil.copytree(src=os.path.join(charts_path, charts_dir), dst=os.path.join(team_charts_path, charts_dir))
    )


def add_repo(repo: str, repo_location: str) -> None:
    _logger.debug("Adding Helm Repository: %s at %s", repo, repo_location)
    sh.run(f"helm repo add {repo} {repo_location}")


def init_env_repo(context: Context) -> str:
    repo_location = f"s3://{context.toolkit.s3_bucket}/helm/repositories/env"
    if not s3.object_exists(bucket=cast(str, context.toolkit.s3_bucket), key="helm/repositories/env/index.yaml"):
        _logger.debug("Initializing Env Helm Respository at %s", repo_location)
        sh.run(f"helm s3 init {repo_location}")
    else:
        _logger.debug("Skipping initialization of existing Env Helm Repository at %s", repo_location)

    context.helm_repository = repo_location
    return repo_location


def init_team_repo(context: Context, team_context: TeamContext) -> str:
    repo_location = f"s3://{context.toolkit.s3_bucket}/helm/repositories/teams/{team_context.name}"
    if not s3.object_exists(
        bucket=cast(str, context.toolkit.s3_bucket), key=f"helm/repositories/teams/{team_context.name}/index.yaml"
    ):
        _logger.debug("Initializing Team Helm Respository at %s", repo_location)
        sh.run(f"helm s3 init {repo_location}")
    else:
        _logger.debug("Skipping initialization of existing Team Helm Repository at %s", repo_location)

    team_context.helm_repository = repo_location
    return repo_location


def package_chart(repo: str, chart_path: str, values: Optional[Dict[str, Any]]) -> Tuple[str, str, str]:
    chart_yaml = os.path.join(chart_path, "Chart.yaml")
    values_yaml = os.path.join(chart_path, "values.yaml")

    chart_version = aws_orbit.__version__.replace(".dev", "-")
    chart = yaml.safe_load(
        update_file(chart_yaml, {"orbit_version": aws_orbit.__version__, "chart_version": chart_version})
    )
    chart_version = chart["version"]

    if values:
        update_file(values_yaml, values)

    chart_name = chart_path.split("/")[-1]
    _logger.debug("Packaging %s at %s", chart_name, chart_path)
    for line in sh.run_iterating(f"helm package --debug {chart_path}"):
        if line.startswith("Successfully packaged chart and saved it to: "):
            chart_package = line.replace("Successfully packaged chart and saved it to: ", "")
            _logger.debug("Created package: %s", chart_package)

    _logger.debug("Pusing %s to %s repository", chart_package, repo)
    sh.run(f"helm s3 push --force {chart_package} {repo}")
    return chart_name, chart_version, chart_package


def install_chart(repo: str, namespace: str, name: str, chart_name: str, chart_version: str) -> None:
    chart_version = aws_orbit.__version__.replace(".dev", "-")
    _logger.debug("Installing %s, version %s as %s from %s", chart_name, chart_version, name, repo)
    sh.run(
        f"helm upgrade --install --debug --namespace {namespace} --version "
        f"{chart_version} {name} {repo}/{chart_name}"
    )


def install_chart_no_upgrade(repo: str, namespace: str, name: str, chart_name: str, chart_version: str) -> None:
    chart_version = aws_orbit.__version__.replace(".dev", "-")
    _logger.debug("Installing %s, version %s as %s from %s", chart_name, chart_version, name, repo)
    sh.run(f"helm install --debug --namespace {namespace} --version {chart_version} {name} {repo}/{chart_name}")


def uninstall_chart(name: str, namespace: str ) -> None:
    try:
        _logger.debug("Uninstalling %s", name)
        sh.run(f"helm uninstall --debug {name} -n {namespace}")
    except exceptions.FailedShellCommand as e:
        _logger.error(e)


def is_exists_chart_release(name: str, namespace: str) -> bool:
    try:
        _logger.info("Installed charts at %s", namespace)
        found = False
        for line in sh.run_iterating(f"helm list -n {namespace}"):
            _logger.info(line)
            if name in line:
                found = True

        return found
    except exceptions.FailedShellCommand as e:
        _logger.error(e)
        raise e


def delete_chart(repo: str, chart_name: str) -> None:
    try:
        _logger.debug("Deleting %s from %s repository", chart_name, repo)
        sh.run(f"helm s3 delete {chart_name} {repo}")
    except exceptions.FailedShellCommand as e:
        _logger.error(e)


def deploy_env(context: Context) -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        repo_location = init_env_repo(context=context)
        repo = context.name
        add_repo(repo=repo, repo_location=repo_location)
        kubectl.write_kubeconfig(context=context)

        if context.install_image_replicator or not context.networking.data.internet_accessible:
            chart_name, chart_version, chart_package = package_chart(
                repo=repo,
                chart_path=os.path.join(CHARTS_PATH, "env", "image-replicator"),
                values={
                    "region": context.region,
                    "account_id": context.account_id,
                    "env_name": context.name,
                    "repository": context.images.image_replicator.repository,
                    "tag": context.images.image_replicator.version,
                    "sts_ep": "legacy" if context.networking.data.internet_accessible else "regional",
                    "image_pull_policy": "Always" if aws_orbit.__version__.endswith(".dev0") else "IfNotPresent",
                },
            )
            install_chart(
                repo=repo,
                namespace="orbit-system",
                name="image-replicator",
                chart_name=chart_name,
                chart_version=chart_version,
            )


def deploy_team(context: Context, team_context: TeamContext) -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        repo_location = init_team_repo(context=context, team_context=team_context)
        repo = team_context.name
        add_repo(repo=repo, repo_location=repo_location)
        kubectl.write_kubeconfig(context=context)

        team_charts_path = create_team_charts_copy(team_context=team_context, path=os.path.join(CHARTS_PATH, "team"))
        package_team_space_pkg(context, repo, team_charts_path, team_context)
        package_user_space_pkg(context, repo, team_charts_path, team_context)

def package_team_space_pkg(context, repo, team_charts_path, team_context):
    chart_name, chart_version, chart_package = package_chart(
        repo=repo,
        chart_path=os.path.join(team_charts_path, "team-settings"),
        values={
            "env_name": context.name,
            "team": team_context.name,
            "efsid": context.shared_efs_fs_id,
            "efsapid": team_context.efs_ap_id,
            "region": context.region,
            "cluster_pod_security_group_id": context.cluster_pod_sg_id,
            "team_security_group_id": team_context.team_security_group_id,
            "grant_sudo": '"yes"' if team_context.grant_sudo else '"no"',
            "sts_ep": "legacy" if context.networking.data.internet_accessible else "regional",
            "team_role_arn": team_context.eks_pod_role_arn,
        },
    )
    install_chart(
        repo=repo, namespace=team_context.name, name="team-settings", chart_name=chart_name, chart_version=chart_version
    )

def package_user_space_pkg(context, repo, team_charts_path, team_context):
    chart_name, chart_version, chart_package = package_chart(
        repo=repo,
        chart_path=os.path.join(team_charts_path, "orbit-user"),
        values={
            "env_name": context.name,
            "team": team_context.name,
            "efsid": context.shared_efs_fs_id,
            "efsapid": team_context.efs_ap_id,
            "region": context.region,
            "cluster_pod_security_group_id": context.cluster_pod_sg_id,
            "team_security_group_id": team_context.team_security_group_id,
            "grant_sudo": '"yes"' if team_context.grant_sudo else '"no"',
            "sts_ep": "legacy" if context.networking.data.internet_accessible else "regional",
            "team_role_arn": team_context.eks_pod_role_arn,
        },
    )


def destroy_env(context: Context) -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        repo_location = init_env_repo(context=context)
        repo = context.name
        add_repo(repo=repo, repo_location=repo_location)
        kubectl.write_kubeconfig(context=context)
        uninstall_chart(name="image-replicator", namespace="orbit-system")

def destroy_team(context: Context, team_context: TeamContext) -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        repo_location = init_team_repo(context=context, team_context=team_context)
        repo = team_context.name
        add_repo(repo=repo, repo_location=repo_location)
        kubectl.write_kubeconfig(context=context)
        uninstall_chart(name=f"{team_context.name}-jupyter-hub", namespace=team_context.name)
        uninstall_chart(name="team-settings", namespace=team_context.name)