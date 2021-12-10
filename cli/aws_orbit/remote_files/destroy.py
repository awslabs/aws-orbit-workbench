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
import time
from typing import Tuple

from softwarelabs_remote_toolkit import remotectl

from aws_orbit import ORBIT_CLI_ROOT, cleanup, plugins, sh
from aws_orbit.exceptions import FailedShellCommand
from aws_orbit.models.context import Context, ContextSerDe, FoundationContext
from aws_orbit.remote_files import cdk_toolkit, eksctl, env, foundation, helm, kubectl, teams
from aws_orbit.services import ecr, secretsmanager, ssm

_logger: logging.Logger = logging.getLogger(__name__)


def delete_image(args: Tuple[str, ...]) -> None:
    _logger.debug("args %s", args)
    env_name: str = args[0]
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)

    if len(args) == 2:
        image_name: str = args[1]
    else:
        raise ValueError("Unexpected number of values in args.")

    env.deploy(context=context, eks_system_masters_roles_changes=None)
    _logger.debug("Env changes deployed")
    ecr.delete_repo(repo=f"orbit-{context.name}/{image_name}")
    _logger.debug("Docker Image Destroyed from ECR")


def destroy_team_user_resources(team_name: str) -> None:
    try:
        sh.run(
            f"bash -c 'for ns in $(kubectl get namespaces --output=jsonpath={{.items..metadata.name}} "
            f"-l orbit/team={team_name},orbit/space=team); "
            f"do kubectl delete teamspace $ns -n $ns  --force; "
            f"done'"
        )
    except FailedShellCommand:
        _logger.error("Failed toexecute command to delete teamspace object: %s")


def destroy_teams(env_name: str) -> None:
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("context.name %s", context.name)

    @remotectl.remote_function(
        "orbit",
        codebuild_role=context.toolkit.admin_role,
        extra_local_modules={
            "aws-orbit-jupyterlab-orbit": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../jupyterlab_orbit")),
            "aws-orbit-emr-on-eks": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/emr_on_eks")),
            "aws-orbit-custom-cfn": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/custom_cfn")),
            "aws-orbit-hello-world": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/hello_world")),
            "aws-orbit-lustre": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/lustre")),
            "aws-orbit-overprovisioning": os.path.realpath(
                os.path.join(ORBIT_CLI_ROOT, "../../plugins/overprovisioning")
            ),
            "aws-orbit-ray": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/ray")),
            "aws-orbit-redshift": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/redshift")),
            "aws-orbit-sm-operator": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/sm-operator")),
            "aws-orbit-team-script-launcher": os.path.realpath(
                os.path.join(ORBIT_CLI_ROOT, "../../plugins/team_script_launcher")
            ),
            "aws-orbit-voila": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/voila")),
            "aws-orbit-code-commit": os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../plugins/code_commit")),
        },
    )
    def destroy_teams(env_name: str) -> None:
        plugins.PLUGINS_REGISTRIES.load_plugins(context=context, plugin_changesets=[], teams_changeset=None)
        kubectl.write_kubeconfig(context=context)
        for team_context in context.teams:
            destroy_team_user_resources(team_context.name)
        time.sleep(60)
        _logger.debug("Plugins loaded")
        for team_context in context.teams:
            plugins.PLUGINS_REGISTRIES.destroy_team_plugins(context=context, team_context=team_context)
        _logger.debug("Plugins destroyed")
        for team_context in context.teams:
            helm.destroy_team(context=context, team_context=team_context)
        _logger.debug("Helm Charts uninstalled")
        kubectl.destroy_teams(context=context)
        _logger.debug("Kubernetes Team components destroyed")
        eksctl.destroy_teams(context=context)
        _logger.debug("EKS Team Stacks destroyed")
        teams.destroy_all(context=context)
        _logger.debug("Teams Stacks destroyed")
        ssm.cleanup_teams(env_name=context.name)

    destroy_teams(env_name=env_name)


def destroy_env(env_name: str) -> None:

    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("context.name %s", context.name)

    @remotectl.remote_function("orbit", codebuild_role=context.toolkit.admin_role)
    def destroy_env(env_name: str) -> None:

        # Helps save time on target group issues with vpc
        cleanup.delete_istio_ingress(context=context)
        cleanup.delete_target_group(cluster_name=context.env_stack_name)

        # Delete the optional Fargate Profile
        cleanup.delete_system_fargate_profile(context=context)

        # Delete istio-system pod disruption budget; Causes a dead lock
        cleanup.delete_istio_pod_disruption_budget(context=context)

        # helm.destroy_env(context=context)
        # _logger.debug("Helm Charts uninstalled")

        # kubeflow.destroy_kubeflow(context=context)
        # _logger.debug("Kubeflow uninstalled")

        # kubectl.destroy_env(context=context)
        # _logger.debug("Kubernetes Environment components destroyed")

        eksctl.destroy_env(context=context)
        _logger.debug("EKS Environment Stacks destroyed")

        cleanup.delete_elb_security_group(cluster_name=context.env_stack_name)

        env.destroy(context=context)
        _logger.debug("Env Stack destroyed")
        cdk_toolkit.destroy(context=context)
        _logger.debug("CDK Toolkit Stack destroyed")

    destroy_env(env_name=env_name)


def destroy_foundation(env_name: str) -> None:
    context: "FoundationContext" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=FoundationContext)
    _logger.debug("context.name %s", context.name)

    @remotectl.remote_function("orbit", codebuild_role=context.toolkit.admin_role)
    def destroy_foundation(env_name: str) -> None:
        foundation.destroy(context=context)
        _logger.debug("Demo Stack destroyed")
        cdk_toolkit.destroy(context=context)
        _logger.debug("CDK Toolkit Stack destroyed")

    destroy_foundation(env_name)


def destroy_credentials(env_name: str, registry: str) -> None:
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("Context loaded.")

    @remotectl.remote_function("orbit", codebuild_role=context.toolkit.admin_role)
    def destroy_credentials(env_name: str, registry: str) -> None:
        secret_id = f"orbit-{env_name}-docker-credentials"
        credentials = secretsmanager.get_secret_value(secret_id=secret_id)

        if registry in credentials:
            del credentials[registry]
            secretsmanager.put_secret_value(secret_id=secret_id, secret=credentials)
            _logger.debug("Registry Credentials destroyed")
        else:
            _logger.debug("Registry Credentials not found, ignoring")

    destroy_credentials(env_name=env_name, registry=registry)


def destroy_images(env: str) -> None:
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
    _logger.debug("env %s", env)

    @remotectl.remote_function("orbit", codebuild_role=context.toolkit.admin_role)
    def destroy_images(env: str) -> None:
        ecr.cleanup_remaining_repos(env_name=env)

    destroy_images(env=env)
