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
import threading
from typing import Tuple

from aws_orbit import cleanup, plugins, sh
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
    thread_name = threading.current_thread().name
    _logger.debug("Destroying all %s resources using thread %s", team_name, thread_name)
    # Force delete any Pods belonging to the Team in an attempt to eliminate Termination hangs
    for resource in [
        "hyperparametertuningjob.sagemaker.aws.amazon.com",
        "trainingjobs.sagemaker.aws.amazon.com",
        "batchtransformjob.sagemaker.aws.amazon.com",
        "hostingdeployment.sagemaker.aws.amazon.com",
        "jobs",
        "notebooks",
        "deployments",
        "statefulsets",
        "pods",
    ]:
        _logger.debug("Force deleting %s for Team %s", resource, team_name)
        try:
            sh.run(
                f"bash -c 'for ns in $(kubectl get namespaces --output=jsonpath={{.items..metadata.name}} "
                f"-l orbit/team={team_name}); "
                f"do kubectl delete {resource} -n $ns --all --force; sleep 10; "
                f"done'"
            )
        except FailedShellCommand:
            _logger.debug("Ignoring failed deletion of: %s", resource)

    # Get rid of any pods stuck  in 'Pending' state
    try:
        sh.run(
            f"bash -c 'for p in $(kubectl get pods --field-selector=status.phase=Pending -n {team_name} "
            f"--output=jsonpath={{.items..metadata.name}}); "
            f"do kubectl delete pod $p -n {team_name} --force; sleep 2; "
            f"done'"
        )
    except FailedShellCommand:
        _logger.debug("Ignoring failed deletion of Pending Pods in: %s", team_name)

    try:
        sh.run(f"kubectl delete namespaces -l orbit/team={team_name},orbit/space=user --wait=true")
    except FailedShellCommand:
        _logger.debug("Ignoring failed deletion of namespace: %s", team_name)
    _logger.debug("Destroyed all %s resources using thread %s", team_name, thread_name)


def destroy_teams(args: Tuple[str, ...]) -> None:
    _logger.debug("args %s", args)
    env_name: str = args[0]
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("context.name %s", context.name)
    plugins.PLUGINS_REGISTRIES.load_plugins(context=context, plugin_changesets=[], teams_changeset=None)
    kubectl.write_kubeconfig(context=context)
    threads = []
    # Create thread per team
    for team_context in context.teams:
        _logger.debug("Destroy all user namespaces for %s", team_context.name)
        thread = threading.Thread(target=destroy_team_user_resources, args=(team_context.name,))
        threads.append(thread)
        thread.start()
    # Wait for threads to finish
    for thread in threads:
        thread.join()
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


def destroy_env(args: Tuple[str, ...]) -> None:
    _logger.debug("args %s", args)
    env_name: str = args[0]
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("context.name %s", context.name)

    # Helps save time on target group issues with vpc
    cleanup.delete_istio_ingress(context=context)
    cleanup.delete_target_group(cluster_name=context.env_stack_name)

    # Delete the optional Fargate Profile
    cleanup.delete_system_fargate_profile(context=context)

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


def destroy_foundation(args: Tuple[str, ...]) -> None:
    _logger.debug("args %s", args)
    env_name: str = args[0]
    context: "FoundationContext" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=FoundationContext)
    _logger.debug("context.name %s", context.name)

    foundation.destroy(context=context)
    _logger.debug("Demo Stack destroyed")
    cdk_toolkit.destroy(context=context)
    _logger.debug("CDK Toolkit Stack destroyed")


def destroy_credentials(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    if len(args) != 2:
        raise ValueError("Unexpected number of values in args")
    env_name: str = args[0]
    registry: str = args[1]
    _logger.debug("Context loaded.")

    secret_id = f"orbit-{env_name}-docker-credentials"
    credentials = secretsmanager.get_secret_value(secret_id=secret_id)

    if registry in credentials:
        del credentials[registry]
        secretsmanager.put_secret_value(secret_id=secret_id, secret=credentials)
        _logger.debug("Registry Credentials destroyed")
    else:
        _logger.debug("Registry Credentials not found, ignoring")
