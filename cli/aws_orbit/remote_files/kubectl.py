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
import time
from typing import Any, Dict, List, Optional, Tuple, cast

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


def _generate_orbit_system_kustomizations(context: "Context", clean_up: bool = True) -> List[str]:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "orbit-system")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)

    commons_output_path = _generate_orbit_system_commons_manifest(output_path=output_path, context=context)

    return [commons_output_path]


def _orbit_system_commons_base(output_path: str, context: Context) -> None:
    os.makedirs(os.path.join(output_path, "base"), exist_ok=True)
    filenames = ["kustomization.yaml", "00a-commons.yaml", "00b-cert-manager.yaml"]
    for filename in filenames:
        input = os.path.join(MODELS_PATH, "orbit-system", "commons", "base", filename)
        output = os.path.join(output_path, "base", filename)
        with open(input, "r") as file:
            content: str = file.read()
        content = resolve_parameters(
            content,
            dict(account_id=context.account_id, region=context.region, env_name=context.name, secure_port="10260"),
        )
        with open(output, "w") as file:
            file.write(content)


def _generate_orbit_system_commons_manifest(output_path: str, context: "Context") -> str:
    output_path = os.path.join(output_path, "commons")
    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    _orbit_system_commons_base(output_path=output_path, context=context)
    overlays_path = os.path.join(output_path, "overlays")
    src = (
        os.path.join(MODELS_PATH, "orbit-system", "commons", "overlays", "private")
        if context.networking.data.internet_accessible
        else os.path.join(MODELS_PATH, "orbit-system", "commons", "overlays", "isolated")
    )
    shutil.copytree(
        src=src,
        dst=overlays_path,
    )
    return overlays_path


def _kubeflow_namespaces(context: "Context", clean_up: bool = True) -> str:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "orbit-system")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)

    filenames = ["kubeflow_namespace.yaml"]

    for filename in filenames:
        input = os.path.join(MODELS_PATH, "kubeflow", filename)
        output = os.path.join(output_path, filename)

        with open(input, "r") as file:
            content: str = file.read()
        content = resolve_parameters(
            content,
            dict(
                env_name=context.name,
                account_id=context.account_id,
                region=context.region,
                sts_ep="legacy" if context.networking.data.internet_accessible else "regional",
            ),
        )
        with open(output, "w") as file:
            file.write(content)

    return output_path


def _orbit_controller(context: "Context", output_path: str) -> None:
    filenames = ["01a-orbit-controller.yaml"]

    for filename in filenames:
        input = os.path.join(MODELS_PATH, "orbit-system", filename)
        output = os.path.join(output_path, filename)

        with open(input, "r") as file:
            content: str = file.read()
        content = resolve_parameters(
            content,
            dict(
                env_name=context.name,
                code_build_image=f"{context.images.code_build.repository}:" f"{context.images.code_build.version}",
                orbit_controller_image=f"{context.images.orbit_controller.repository}:"
                f"{context.images.orbit_controller.version}",
                k8s_utilities_image=f"{context.images.k8s_utilities.repository}:"
                f"{context.images.k8s_utilities.version}",
                image_pull_policy="Always" if aws_orbit.__version__.endswith(".dev0") else "IfNotPresent",
                account_id=context.account_id,
                region=context.region,
                sts_ep="legacy" if context.networking.data.internet_accessible else "regional",
            ),
        )
        with open(output, "w") as file:
            file.write(content)


def _orbit_image_replicator(context: "Context", output_path: str) -> None:
    filenames = ["01b-image-replicator.yaml"]

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
            ),
        )
        with open(output, "w") as file:
            file.write(content)


def _ssm_agent_installer(output_path: str, context: "Context") -> None:
    filename = "02a-ssm-agent-daemonset-installer.yaml"
    input = os.path.join(MODELS_PATH, "orbit-system", filename)
    output = os.path.join(output_path, filename)
    shutil.copyfile(src=input, dst=output)


def _sm_operator_installer(output_path: str, context: "Context") -> None:
    filename = "10a-sm-operator.yaml"
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
            region=context.region,
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
                region=context.region,
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

    _orbit_controller(context=context, output_path=output_path)

    if context.install_ssm_agent:
        _logger.debug("Deploying SSM Agent Installer")
        _ssm_agent_installer(output_path=output_path, context=context)
    else:
        _logger.debug("Skipping deployment of SSM Agent Installer")

    _sm_operator_installer(output_path=output_path, context=context)

    return output_path


def _generate_orbit_image_replicator_manifest(context: "Context", clean_up: bool = True) -> Optional[str]:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "orbit-system")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)

    if context.install_image_replicator or not context.networking.data.internet_accessible:
        _logger.debug("Deploying Pod Image Modifier and Image Replicator")
        _orbit_image_replicator(output_path=output_path, context=context)
        return output_path
    else:
        _logger.debug("Skipping deployment of Pod Image Modifier and Image Replicator")
        return None


def _generate_orbit_system_env_kustomizations(context: "Context", clean_up: bool = True) -> List[str]:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "env")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)

    env_output_path = _generate_orbit_system_env_manifest(output_path=output_path, context=context)

    return [env_output_path]


def _orbit_system_env_base(output_path: str, context: Context) -> None:
    os.makedirs(os.path.join(output_path, "base"), exist_ok=True)
    filenames = ["kustomization.yaml", "00-commons.yaml"]
    for filename in filenames:
        input = os.path.join(MODELS_PATH, "env", "base", filename)
        output = os.path.join(output_path, "base", filename)
        with open(input, "r") as file:
            content: str = file.read()
        content = utils.resolve_parameters(
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


def _generate_orbit_system_env_manifest(output_path: str, context: "Context") -> str:
    _cleanup_output(output_path=output_path)
    _orbit_system_env_base(output_path=output_path, context=context)
    overlays_path = os.path.join(output_path, "overlays")
    src = (
        os.path.join(MODELS_PATH, "env", "overlays", "private")
        if context.networking.data.internet_accessible
        else os.path.join(MODELS_PATH, "env", "overlays", "isolated")
    )
    shutil.copytree(
        src=src,
        dst=overlays_path,
    )
    return overlays_path


def _generate_kubeflow_patch(context: "Context", clean_up: bool = True) -> Tuple[str, str]:
    output_path = os.path.join(".orbit.out", context.name, "kubectl", "env")
    os.makedirs(output_path, exist_ok=True)
    if clean_up:
        _cleanup_output(output_path=output_path)

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

    with open(input, "r") as file:
        patch = file.read()

    return output, patch


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

    if context.networking.frontend.custom_domain_name:
        context.landing_page_url = f"https://{context.networking.frontend.custom_domain_name}"
    else:
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


# Confirm orbit-system Service Endpoints
def _confirm_endpoints(name: str, namespace: str, k8s_context: str) -> None:
    addresses = k8s.get_service_addresses(name=name, namespace=namespace, k8s_context=k8s_context)
    if addresses:
        for address in addresses:
            _logger.debug(
                "Service: %s Namespace: %s Hostname: %s IP: %s",
                name,
                namespace,
                address.get("hostname"),
                address.get("ip"),
            )
    else:
        raise Exception("No Endpoints found for Service: %s Namespace: %s", name, namespace)


def _confirm_readiness(name: str, namespace: str, type: str, k8s_context: str) -> None:
    for _ in range(20):
        status = k8s.get_resource_status(name=name, namespace=namespace, type=type, k8s_context=k8s_context)
        ready_replicas = status.get("ready_replicas")
        if ready_replicas and int(ready_replicas) > 0:
            _logger.debug("%s/%s ready", namespace, name)
            break
        else:
            _logger.debug("%s/%s not yet ready, sleeping for 1 minute", namespace, name)
            time.sleep(60)
    else:
        raise Exception("Timeout wating for Image Replicator to become ready")


def write_kubeconfig(context: "Context") -> None:
    sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")


def deploy_env(context: "Context") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        k8s_context = get_k8s_context(context=context)
        _logger.debug("k8s_context: %s", k8s_context)

        # orbit-system kustomizations
        output_paths = _generate_orbit_system_kustomizations(context=context)
        for path in output_paths:
            sh.run(f"kubectl apply -k {path} --context {k8s_context} --wait")

        # Wait until cert-manager webhook is available
        _confirm_endpoints(name="cert-manager-webhook", namespace="cert-manager", k8s_context=k8s_context)
        _confirm_readiness(name="cert-manager", namespace="cert-manager", type="Deployment", k8s_context=k8s_context)
        _confirm_readiness(
            name="cert-manager-cainjector", namespace="cert-manager", type="Deployment", k8s_context=k8s_context
        )

        output_path: Optional[str] = _generate_orbit_system_manifest(context=context, clean_up=True)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        output_path = _generate_orbit_image_replicator_manifest(context=context, clean_up=True)
        if output_path is not None:
            sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        # Restart orbit-system deployments and statefulsets to force reload of caches etc
        # sh.run(f"kubectl rollout restart deployments -n orbit-system --context {k8s_context}")
        # sh.run(f"kubectl rollout restart statefulsets -n orbit-system --context {k8s_context}")

        _confirm_endpoints(name="podsettings-pod-modifier", namespace="orbit-system", k8s_context=k8s_context)

        if context.install_image_replicator or not context.networking.data.internet_accessible:
            _confirm_endpoints(name="pod-image-updater", namespace="orbit-system", k8s_context=k8s_context)
            _confirm_readiness(
                name="pod-image-replicator", namespace="orbit-system", type="statefulset", k8s_context=k8s_context
            )
            sh.run(
                "kubectl rollout restart daemonsets -n orbit-system-ssm-daemons "
                f"ssm-agent-installer --context {k8s_context}"
            )

        # kube-system kustomizations
        output_paths = _generate_kube_system_kustomizations(context=context)
        for output_path in output_paths:
            sh.run(f"kubectl apply -k {output_path} --context {k8s_context} --wait")

        # kube-system manifests
        output_path = _generate_kube_system_manifest(context=context)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        # Enable ENIs
        sh.run(f"kubectl set env daemonset aws-node -n kube-system --context {k8s_context} ENABLE_POD_ENI=true")
        sh.run(
            f"kubectl set env daemonset aws-node -n kube-system --context {k8s_context} DISABLE_TCP_EARLY_DEMUX=true"
        )

        # kubeflow-namespaces
        output_path = _kubeflow_namespaces(context=context)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        kubeflow.deploy_kubeflow(context=context)

        # env
        output_paths = _generate_orbit_system_env_kustomizations(context=context)
        for output_path in output_paths:
            sh.run(f"kubectl apply -k {output_path} --context {k8s_context} --wait")

        # Patch Kubeflow
        _logger.debug("Orbit applying KubeFlow patch")
        jupyter_launcher_config_map, patch = _generate_kubeflow_patch(context=context)
        sh.run(f"kubectl apply -f {jupyter_launcher_config_map} --context {k8s_context} --wait")
        sh.run(f'kubectl patch deployment -n kubeflow jupyter-web-app-deployment --patch "{patch}"')
        sh.run("kubectl rollout restart deployment jupyter-web-app-deployment -n kubeflow")

        # Patch Pods to push into Fargate when deploying in an isolated subnet
        if not context.networking.data.internet_accessible:
            patch = '{"spec":{"template":{"metadata":{"labels":{"orbit/node-type":"fargate"}}}}}'
            sh.run(f"kubectl patch deployment -n istio-system authzadaptor --patch '{patch}'")

            patch = (
                '{"spec":{"template":{"metadata":{"labels":{"orbit/node-type":"fargate"}},'
                '"spec":{"containers":[{"name":"alb-ingress-controller","args":["--ingress-class=alb"'
                ',"--cluster-name=$(CLUSTER_NAME)","--aws-vpc-id=VPC_ID"]}]}}}}'
            )
            patch = patch.replace("VPC_ID", cast(str, context.networking.vpc_id))
            sh.run(f"kubectl patch deployment -n kubeflow alb-ingress-controller --patch '{patch}'")

            # patch = (
            #     '[{"op": "add", "path": "/spec/template/metadata/labels/orbit~1node-type", "value": "fargate"}, '
            #     '{"op": "replace", "path": "/spec/template/spec/nodeSelector", "value": {}}]'
            # )
            # sh.run(f"kubectl patch deployment -n orbit-system landing-page-service --type json --patch '{patch}'")

        # Confirm env Service Endpoints
        # Patch the alb-controller specifically to run in the env nodegroup IF we do have internet access
        if context.networking.data.internet_accessible:
            _logger.debug("Orbit applying KubeFlow patch to ALB Controller with Internet Access")
            patch = (
                '{"spec":{"template":{"metadata":{"labels":{"orbit/node-type":"ec2"}},'
                '"spec":{"nodeSelector":{"orbit/usage":"reserved","orbit/node-group": "env"}}}}}'
            )
            sh.run(f"kubectl patch deployment -n kubeflow alb-ingress-controller --patch '{patch}'")

        _confirm_endpoints(name="landing-page-service", namespace="orbit-system", k8s_context=k8s_context)


def deploy_team(context: "Context", team_context: "TeamContext") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl context: %s", k8s_context)
        output_path = _generate_team_context(context=context, team_context=team_context)
        sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        # (output_path, patch) = _generate_env_manifest(context=context, clean_up=False)
        # sh.run(f"kubectl apply -f {output_path} --context {k8s_context} --wait")

        # Patch Kubeflow
        # _logger.debug("Orbit applying KubeFlow patch")
        # sh.run(f'kubectl patch deployment jupyter-web-app-deployment --patch "{patch}" -n kubeflow')
        # sh.run("kubectl rollout restart deployment jupyter-web-app-deployment -n kubeflow")


def destroy_env(context: "Context") -> None:
    eks_stack_name: str = f"eksctl-orbit-{context.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)
    if cfn.does_stack_exist(stack_name=eks_stack_name):
        sh.run(f"eksctl utils write-kubeconfig --cluster orbit-{context.name} --set-kubeconfig-context")
        k8s_context = get_k8s_context(context=context)
        _logger.debug("kubectl k8s_context: %s", k8s_context)
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

            output_path = _generate_orbit_system_manifest(context=context)
            sh.run(
                f"kubectl delete -f {output_path} --grace-period=0 --force "
                f"--ignore-not-found --wait --context {k8s_context}"
            )
            output_paths = _generate_orbit_system_kustomizations(context=context, clean_up=True)
            for output_path in output_paths:
                sh.run(
                    f"kubectl delete -k {output_path} --grace-period=0 --force "
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
