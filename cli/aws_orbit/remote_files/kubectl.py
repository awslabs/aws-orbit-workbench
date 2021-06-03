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
from typing import Any, Dict, List, Tuple

import aws_orbit
from aws_orbit import ORBIT_CLI_ROOT, exceptions, k8s, sh, utils
from aws_orbit.exceptions import FailedShellCommand
from aws_orbit.models.context import Context, ContextSerDe, TeamContext
from aws_orbit.remote_files import kubeflow
from aws_orbit.remote_files.utils import get_k8s_context
from aws_orbit.services import cfn, elb
from aws_orbit.utils import resolve_parameters

_logger: logging.Logger = logging.getLogger(__name__)


MODELS_PATH = os.path.join(ORBIT_CLI_ROOT, "data", "kubectl")


def _orbit_system_commons(context: "Context", output_path: str) -> None:
    filename = "00-commons.yaml"
    input = os.path.join(MODELS_PATH, "orbit-system", filename)
    output = os.path.join(output_path, filename)

    with open(input, "r") as file:
        content: str = file.read()
    content = resolve_parameters(
        content,
        dict(
            account_id=context.account_id,
            region=context.region,
            env_name=context.name,
        ),
    )
    with open(output, "w") as file:
        file.write(content)


def _orbit_controller(context: "Context", output_path: str) -> None:
    filenames = ["01a-orbit-controller.yaml", "01b-cert-manager.yaml"]

    for filename in filenames:
        input = os.path.join(MODELS_PATH, "orbit-system", filename)
        output = os.path.join(output_path, filename)

        with open(input, "r") as file:
            content: str = file.read()
        content = resolve_parameters(
            content,
            dict(
                env_name=context.name,
                orbit_controller_image=f"{context.images.orbit_controller.repository}:"
                f"{context.images.orbit_controller.version}",
                k8s_utilities_image=f"{context.images.k8s_utilities.repository}:"
                f"{context.images.k8s_utilities.version}",
                image_pull_policy="Always" if aws_orbit.__version__.endswith(".dev0") else "IfNotPresent",
                certArn=context.networking.frontend.ssl_cert_arn,
                cognitoAppClientId=context.user_pool_client_id,
                cognitoUserPoolID=context.user_pool_id,
                account_id=context.account_id,
                region=context.region,
                cognitoUserPoolDomain=context.cognito_external_provider_domain,
            ),
        )
        with open(output, "w") as file:
            file.write(content)


def _cluster_autoscaler(output_path: str, context: "Context") -> None:
    filename = "02-cluster-autoscaler-autodiscover.yaml"
    input = os.path.join(MODELS_PATH, "kube-system", filename)
    output = os.path.join(output_path, filename)

    with open(input, "r") as file:
        content: str = file.read()
    content = utils.resolve_parameters(
        content,
        dict(
            account_id=context.account_id,
            env_name=context.name,
            cluster_name=f"orbit-{context.name}",
            sts_ep="legacy" if context.networking.data.internet_accessible else "regional",
            image_pull_policy="Always" if aws_orbit.__version__.endswith(".dev0") else "IfNotPresent",
            use_static_instance_list=str(not context.networking.data.internet_accessible).lower(),
        ),
    )
    with open(output, "w") as file:
        file.write(content)


def _ssm_agent_installer(output_path: str, context: "Context") -> None:
    filename = "02-ssm-agent-daemonset-installer.yaml"
    input = os.path.join(MODELS_PATH, "orbit-system", filename)
    output = os.path.join(output_path, filename)
    shutil.copyfile(src=input, dst=output)


def _sm_operator_installer(output_path: str, context: "Context") -> None:
    filename = "10-sm-operator.yaml"
    input = os.path.join(MODELS_PATH, "orbit-system", filename)
    output = os.path.join(output_path, filename)
    shutil.copyfile(src=input, dst=output)


def _team(context: "Context", team_context: "TeamContext", output_path: str) -> None:
    input = os.path.join(MODELS_PATH, "teams", "00-team.yaml")
    output = os.path.join(output_path, f"{team_context.name}-00-team.yaml")

    with open(input, "r") as file:
        content: str = file.read()

    content = utils.resolve_parameters(
        content,
        dict(
            team=team_context.name,
            efsid=context.shared_efs_fs_id,
            efsapid=team_context.efs_ap_id,
            efsprivateapid=team_context.efs_private_ap_id if team_context.efs_private_ap_id else "",
            account_id=context.account_id,
            env_name=context.name,
            team_kms_key_arn=team_context.team_kms_key_arn,
            team_security_group_id=team_context.team_security_group_id,
            cluster_pod_security_group_id=context.cluster_pod_sg_id,
            team_context=ContextSerDe.dump_context_to_str(team_context),
            env_context=ContextSerDe.dump_context_to_str(context),
        ),
    )
    _logger.debug("Kubectl Team %s manifest:\n%s", team_context.name, content)
    with open(output, "w") as file:
        file.write(content)

    # team rbac role
    input = os.path.join(MODELS_PATH, "teams", "01-team-rbac-role.yaml")
    output = os.path.join(output_path, f"{team_context.name}-01-team-rbac-role.yaml")

    with open(input, "r") as file:
        content = file.read()
    content = utils.resolve_parameters(content, dict(team=team_context.name))
    with open(output, "w") as file:
        file.write(content)

    # bind to admin role
    if team_context.k8_admin:
        # user service account
        input = os.path.join(MODELS_PATH, "teams", "02-admin-binding.yaml")
        output = os.path.join(output_path, f"{team_context.name}-02-admin-binding.yaml")

        with open(input, "r") as file:
            content = file.read()
        content = utils.resolve_parameters(content, dict(team=team_context.name))
        with open(output, "w") as file:
            file.write(content)


def _cleanup_output(output_path: str) -> None:
    files = os.listdir(output_path)
    for file in files:
        if file.endswith(".yaml"):
            os.remove(os.path.join(output_path, file))


def _generate_kube_system_kustomizations(context: "Context", clean_up: bool = True) -> List[str]:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "kube-system")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)

    efs_output_path = _generate_efs_driver_manifest(output_path=output_path, context=context)
    fsx_output_path = _generate_fsx_driver_manifest(output_path=output_path, context=context)

    return [efs_output_path, fsx_output_path]


def _generate_kube_system_manifest(context: "Context", clean_up: bool = True) -> str:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "kube-system")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)

    _cluster_autoscaler(output_path=output_path, context=context)

    filenames = [
        "00-observability.yaml",
        "01-aws-vgpu-daemonset.yaml",
        "01-nvidia-daemonset.yaml",
        "02-cluster-autoscaler-autodiscover.yaml",
    ]
    for filename in filenames:
        input = os.path.join(MODELS_PATH, "kube-system", filename)
        output = os.path.join(output_path, filename)

        with open(input, "r") as file:
            content: str = file.read()
        content = utils.resolve_parameters(
            content,
            dict(
                account_id=context.account_id,
                env_name=context.name,
                cluster_name=f"orbit-{context.name}",
                sts_ep="legacy" if context.networking.data.internet_accessible else "regional",
                image_pull_policy="Always" if aws_orbit.__version__.endswith(".dev0") else "IfNotPresent",
                use_static_instance_list=str(not context.networking.data.internet_accessible).lower(),
            ),
        )
        with open(output, "w") as file:
            file.write(content)

    return output_path


def _generate_orbit_system_manifest(context: "Context", clean_up: bool = True) -> str:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "orbit-system")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)
    _orbit_system_commons(context=context, output_path=output_path)
    _orbit_controller(context=context, output_path=output_path)

    if context.account_id is None:
        raise ValueError("context.account_id is None!")
    if context.user_pool_id is None:
        raise ValueError("context.user_pool_id is None!")
    if context.user_pool_client_id is None:
        raise ValueError("context.user_pool_client_id is None!")
    if context.identity_pool_id is None:
        raise ValueError("context.identity_pool_id is None!")

    if context.install_ssm_agent:
        _ssm_agent_installer(output_path=output_path, context=context)

    _sm_operator_installer(output_path=output_path, context=context)

    return output_path


def _generate_env_manifest(context: "Context", clean_up: bool = True) -> Tuple[str, str]:
    filename = "00-commons.yaml"
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "env")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)

    input = os.path.join(MODELS_PATH, "env", filename)
    output = os.path.join(output_path, filename)
    shutil.copyfile(src=input, dst=output)

    # kubeflow jupyter launcher configmap
    input = os.path.join(MODELS_PATH, "kubeflow", "kf-jupyter-launcher.yaml")
    output = os.path.join(output_path, "kf-jupyter-launcher.yaml")

    with open(input, "r") as file:
        content = file.read()

    content = utils.resolve_parameters(
        content,
        dict(
            orbit_jupyter_user_image=f"{context.images.jupyter_user.repository}:{context.images.jupyter_user.version}"
        ),
    )
    with open(output, "w") as file:
        file.write(content)

    input = os.path.join(MODELS_PATH, "kubeflow", "kf-jupyter-patch.yaml")
    output = os.path.join(output_path, "kf-jupyter-patch.yaml")

    with open(input, "r") as file:
        patch = file.read()

    return (output_path, patch)


def _prepare_team_context_path(context: "Context") -> str:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "apps")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    if context.account_id is None:
        raise ValueError("context.account_id is None!")
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


def fetch_kubectl_data(context: "Context", k8s_context: str) -> None:
    _logger.debug("Fetching Kubectl data...")

    ingress_url: str = k8s.get_ingress_dns(name="istio-ingress", k8s_context=k8s_context, namespace="istio-system")

    context.landing_page_url = f"https://{ingress_url}"
    if context.cognito_external_provider:
        context.cognito_external_provider_redirect = context.landing_page_url

    _update_elbs(context=context)

    ContextSerDe.dump_context_to_ssm(context=context)
    _logger.debug("Kubectl data fetched successfully.")


def _efs_driver_base(output_path: str) -> None:
    os.makedirs(os.path.join(output_path, "base"), exist_ok=True)
    filenames = ("csidriver.yaml", "kustomization.yaml", "node.yaml")
    for filename in filenames:
        input = os.path.join(MODELS_PATH, "kube-system", "efs_driver", "base", filename)
        output = os.path.join(output_path, "base", filename)
        _logger.debug("Copying efs driver base file: %s -> %s", input, output)
        shutil.copyfile(src=input, dst=output)


def _generate_efs_driver_manifest(output_path: str, context: "Context") -> str:
    output_path = os.path.join(output_path, "efs_driver")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    if context.account_id is None:
        raise RuntimeError("context.account_id is None!")
    if context.region is None:
        raise RuntimeError("context.region is None!")
    _efs_driver_base(output_path=output_path)
    overlays_path = os.path.join(output_path, "overlays")
    os.makedirs(overlays_path, exist_ok=True)
    shutil.copyfile(
        src=os.path.join(MODELS_PATH, "kube-system", "efs_driver", "overlays", "kustomization.yaml"),
        dst=os.path.join(overlays_path, "kustomization.yaml"),
    )
    return overlays_path


#######
def _fsx_driver_base(output_path: str, context: "Context") -> None:
    os.makedirs(os.path.join(output_path, "base"), exist_ok=True)
    filenames = ["controller.yaml", "csidriver.yaml", "kustomization.yaml", "node.yaml", "rbac.yaml"]
    for filename in filenames:
        input = os.path.join(MODELS_PATH, "kube-system", "fsx_driver", "base", filename)
        output = os.path.join(output_path, "base", filename)
        _logger.debug("Copying fsx driver base file: %s -> %s", input, output)
        with open(input, "r") as file:
            content: str = file.read()
        content = utils.resolve_parameters(
            content,
            dict(
                orbit_cluster_role=context.eks_cluster_role_arn,
            ),
        )
        with open(output, "w") as file:
            file.write(content)


def _generate_fsx_driver_manifest(output_path: str, context: "Context") -> str:
    output_path = os.path.join(output_path, "fsx_driver")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    if context.account_id is None:
        raise RuntimeError("context.account_id is None!")
    if context.region is None:
        raise RuntimeError("context.region is None!")
    _fsx_driver_base(output_path=output_path, context=context)
    overlays_path = os.path.join(output_path, "overlays")
    os.makedirs(overlays_path, exist_ok=True)
    shutil.copyfile(
        src=os.path.join(MODELS_PATH, "kube-system", "fsx_driver", "overlays", "stable", "kustomization.yaml"),
        dst=os.path.join(overlays_path, "kustomization.yaml"),
    )
    return overlays_path


#######
def write_kubeconfig(context: "Context") -> None:
    sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")


def deploy_env(context: "Context") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        k8s_context = get_k8s_context(context=context)
        _logger.debug("k8s_context: %s", k8s_context)

        # kube-system kustomizations
        output_paths = _generate_kube_system_kustomizations(context=context)
        for output_path in output_paths:
            sh.run(f"kubectl apply -k {output_path} --context {k8s_context} --wait")

        # kube-system manifests
        output_path = _generate_kube_system_manifest(context=context)
        sh.run(f"kubectl delete jobs -l app=cert-manager -n orbit-system --context {k8s_context} --wait")
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        kubeflow.deploy_kubeflow(context=context)

        # orbit-system
        output_path = _generate_orbit_system_manifest(context=context)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        # env
        (output_path, patch) = _generate_env_manifest(context=context)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")
        # Patch Kubeflow
        _logger.debug("Orbit applying KubeFlow patch")
        sh.run(f'kubectl patch deployment jupyter-web-app-deployment --patch "{patch}" -n kubeflow')
        sh.run("kubectl rollout restart deployment jupyter-web-app-deployment -n kubeflow")
        # Enable ENIs
        sh.run(f"kubectl set env daemonset aws-node -n kube-system --context {k8s_context} ENABLE_POD_ENI=true")

        # Restart orbit-system deployments and statefulsets to force reload of caches etc
        sh.run(f"kubectl rollout restart deployments -n orbit-system --context {k8s_context}")
        sh.run(f"kubectl rollout restart statefulsets -n orbit-system --context {k8s_context}")


def deploy_team(context: "Context", team_context: "TeamContext") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl context: %s", k8s_context)
        output_path = _generate_team_context(context=context, team_context=team_context)

        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        (output_path, patch) = _generate_env_manifest(context=context, clean_up=False)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        # Patch Kubeflow
        _logger.debug("Orbit applying KubeFlow patch")
        sh.run(f'kubectl patch deployment jupyter-web-app-deployment --patch "{patch}" -n kubeflow')
        sh.run("kubectl rollout restart deployment jupyter-web-app-deployment -n kubeflow")


def destroy_env(context: "Context") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl k8s_context: %s", k8s_context)
        output_path = _generate_orbit_system_manifest(context=context)
        try:
            # Here we remove some finalizers that can cause our delete to hang indefinitely
            try:
                sh.run(
                    "kubectl patch crd/trainingjobs.sagemaker.aws.amazon.com "
                    '--patch \'{"metadata":{"finalizers":[]}}\' --type=merge'
                    f" --context {k8s_context}"
                )
            except FailedShellCommand:
                _logger.debug("Ignoring patch failure")

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
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl k8s_context: %s", k8s_context)
        _logger.debug("Attempting kubectl delete")
        output_path = _generate_teams_manifest(context=context)
        utils.print_dir(dir=output_path)
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
        # Destory all related user spaces
        sh.run(f"kubectl delete namespaces -l orbit/team={team_context.name} --context {k8s_context}")
