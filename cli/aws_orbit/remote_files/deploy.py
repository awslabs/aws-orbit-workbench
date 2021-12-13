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
import os
import subprocess
from concurrent.futures import Future
from typing import Any, List, Optional, Tuple, cast

from softwarelabs_remote_toolkit import remotectl

from aws_orbit import ORBIT_CLI_ROOT, bundle, docker, plugins, remote, sh
from aws_orbit.models.changeset import Changeset, load_changeset_from_ssm
from aws_orbit.models.context import Context, ContextSerDe, FoundationContext, TeamContext
from aws_orbit.models.manifest import ImageManifest, ImagesManifest, Manifest, ManifestSerDe
from aws_orbit.remote_files import cdk_toolkit, eksctl, env, foundation, helm, kubectl, teams, utils
from aws_orbit.services import codebuild, ecr, kms, secretsmanager
from aws_orbit.utils import boto3_client, get_account_id, get_region, resolve_parameters

_logger: logging.Logger = logging.getLogger(__name__)


def print_results(msg: str) -> None:
    if msg.startswith("[RESULT] "):
        _logger.info(msg)

def _deploy_image(image_name: str, env: str, build_args: Optional[List[str]], use_cache: bool = True) -> None:
    region = get_region()
    account_id = get_account_id()
    _logger.debug(f"_deploy_image args: {account_id}, {region}, {image_name}, {env} {build_args}")

    docker.login_v2(account_id=account_id, region=region)
    _logger.debug("DockerHub and ECR Logged in")
    _logger.debug("Deploying the %s Docker image", image_name)

    ecr_repo = f"orbit-{env}/{image_name}"
    if not ecr.describe_repositories(repository_names=[ecr_repo]):
        ecr.create_repository(repository_name=ecr_repo)

    _logger.debug("Building and deploy docker image from source...")
    path = os.path.join(os.getcwd(), image_name)
    _logger.debug("path: %s", path)

    docker.deploy_image_from_source(
        dir=path, name=ecr_repo, build_args=build_args, use_cache=use_cache, tag="latest", env=env
    )

    _logger.debug("Docker Image Deployed to ECR")


def _deploy_user_image(image_name: str, path: str, env: str, build_args: Optional[List[str]]) -> None:
    region = get_region()
    account_id = get_account_id()
    _logger.debug(f"_deploy_user_image args: {account_id}, {region}, {image_name}, {env}")

    docker.login_v2(account_id=account_id, region=region)
    _logger.debug("DockerHub and ECR Logged in")
    _logger.debug("Deploying the %s Docker image", image_name)

    ecr_repo = f"orbit-{env}/users/{image_name}"
    if not ecr.describe_repositories(repository_names=[ecr_repo]):
        ecr.create_repository(repository_name=ecr_repo)

    _logger.debug("Building and deploy docker image from source...")
    path = os.path.join(os.getcwd(), image_name)
    _logger.debug("path: %s", path)

    docker.deploy_image_from_source(
        dir=path,
        name=ecr_repo,
        build_args=build_args,
        tag="latest",
        env=env,
    )
    _logger.debug("Docker Image Deployed to ECR")


def _load_toolkit_helper(file_path: str, image_name: str, env: str) -> str:
    with open(file_path, "r") as file:
        helper: str = file.read()
    params = {
        "ACCOUNT_ID": get_account_id(),
        "REGION": get_region(),
        "IMAGE_NAME": image_name,
        "ENV": env,
    }
    t = resolve_parameters(helper, dict(params))
    j = json.loads(t)
    if j.get("extra_dirs"):
        new_extra_dirs = {}
        for e in j["extra_dirs"]:
            key = e
            val = os.path.realpath(os.path.join(ORBIT_CLI_ROOT, j["extra_dirs"][e]))
            new_extra_dirs[key] = val
        _logger.debug(f" new extra dir = {new_extra_dirs}")
        j["extra_dirs"] = new_extra_dirs

    _logger.debug(f"OUT of HELPER {j}")
    return json.dumps(j)


def _deploy_images_batch(
    path: str,
    image_name: str,
    env: str,
    build_execution_role: str,
    build_args: List[str] = [],
) -> List[Tuple[str, str, str]]:
    _logger.debug(f"_deploy_images_batch args: {path} {image_name} {env} {build_execution_role}")
    extra_dirs = {image_name: path}
    pre_build_commands = []
    if os.path.exists(os.path.join(path, "toolkit_helper.json")):
        f = os.path.join(path, "toolkit_helper.json")
        helper = json.loads(_load_toolkit_helper(file_path=f, image_name=image_name, env=env))
        _logger.debug(helper)
        if helper.get("extra_dirs"):
            extra_dirs = {**extra_dirs, **helper["extra_dirs"]}
        if helper.get("build_args"):
            build_args = [*build_args, *helper["build_args"]]
        if helper.get("pre_build_commands"):
            pre_build_commands = [*build_args, *helper["pre_build_commands"]]
    else:
        _logger.debug("No Toolkit Helper")

    _logger.debug(f"extra_dirs: {extra_dirs}")
    _logger.debug(f"build_args: {build_args}")

    @remotectl.remote_function(
        "orbit",
        codebuild_role=build_execution_role,
        extra_dirs=extra_dirs,
        bundle_id=image_name,
        extra_pre_build_commands=pre_build_commands,
    )
    def _deploy_images_batch(
        path: str,
        image_name: str,
        env: str,
        build_execution_role: str,
        build_args: List[str],
    ) -> None:
        _logger.info(f"running ...{image_name} at {path}")
        _deploy_image(image_name=image_name, env=env, build_args=build_args, use_cache=False)

    _deploy_images_batch(path, image_name, env, build_execution_role, build_args)
    ecr_address = f"{get_account_id()}.dkr.ecr.{get_region()}.amazonaws.com"
    remote_name = f"{ecr_address}/orbit-{env}/{image_name}"
    return [image_name, remote_name, "latest"]  # type: ignore


def _deploy_remote_image(
    path: str,
    image_name: str,
    env: str,
    script: Optional[str],
    build_args: Optional[List[str]] = [],
    timeout: int = 120,
) -> None:
    _logger.debug(f"_deploy_remote_image_v2 args: {path} {image_name} {script} {env}")
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
    _logger.debug(f"context loaded: {env}")
    pre_build_commands = []
    extra_dirs = {image_name: path}
    # the script is relative to the bundle on remotectl
    if script:
        pre_build_commands = [f"bash {image_name}/{script}"]
    if os.path.exists(os.path.join(path, "toolkit_helper.json")):
        f = os.path.join(path, "toolkit_helper.json")
        helper = json.loads(_load_toolkit_helper(file_path=f, image_name=image_name, env=env))
        _logger.debug(helper)
        if helper.get("extra_dirs"):
            extra_dirs = {**extra_dirs, **helper["extra_dirs"]}
        if helper.get("build_args"):
            build_args = [*build_args, *helper["build_args"]]  # type: ignore
        if helper.get("pre_build_commands"):
            pre_build_commands = [*build_args, *helper["pre_build_commands"]]  # type: ignore

    else:
        _logger.debug("No Toolkit Helper")

    team_env = os.environ.get("AWS_ORBIT_TEAM_SPACE", None)
    team_role = context.get_team_by_name(team_env).eks_pod_role_arn if team_env else None  # type: ignore
    service_role = team_role if team_role else context.toolkit.admin_role
    _logger.debug(f"service_role: {service_role}")
    _logger.debug(f"extra_dirs: {extra_dirs}")
    _logger.debug(f"build_arg: {build_args}")

    @remotectl.remote_function(
        "orbit",
        codebuild_role=service_role,
        extra_dirs=extra_dirs,
        bundle_id=image_name,
        extra_pre_build_commands=pre_build_commands,
        timeout=timeout,
    )
    def _deploy_remote_image(path: str, image_name: str, env: str, build_args: List[str]) -> None:
        _logger.info(f"running ...{image_name} at {path}")
        _deploy_user_image(path=path, image_name=image_name, env=env, build_args=build_args)

    _deploy_remote_image(path, image_name, env, build_args)


def deploy_images_remotely(env: str, requested_image: Optional[str] = None) -> None:
    _logger.debug(f"deploy_images_remotely args: {env} {requested_image}")
    image_dir = os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../images"))
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)

    _logger.debug(f"context loaded: {env}")
    codebuild_role = str(context.toolkit.admin_role)
    _logger.debug(f"The CODEBUILD_ROLE is {codebuild_role}")

    new_images_manifest = {}

    if requested_image:
        if os.path.isdir(f"{image_dir}/{requested_image}"):
            _logger.debug(f"Request build of single image {requested_image}")
            (image_name, image_addr, version) = _deploy_images_batch(
                path=f"{image_dir}/{requested_image}",
                image_name=requested_image,
                env=env,
                build_execution_role=codebuild_role,
            )
            _logger.debug(f"Returned from _deploy_images_batch: {image_name} {image_addr} {version}")
            im = str(image_name).replace("-", "_")
            new_images_manifest[im] = ImageManifest(repository=str(image_addr), version=str(version))
        else:
            _logger.error("An image was requested to be built, but it doesn't exist in the images/ dir")

    else:
        # first build k8s-utilities
        (image_name, image_addr, version) = _deploy_images_batch(
            path=f"{image_dir}/k8s-utilities",
            image_name="k8s-utilities",
            env=env,
            build_execution_role=codebuild_role,
        )
        _logger.debug(f"Returned from _deploy_images_batch: {image_name} {image_addr} {version}")
        im = str(image_name).replace("-", "_")
        new_images_manifest[im] = ImageManifest(repository=str(image_addr), version=str(version))

        # now build the images dependent on k8s-utilities
        list_subfolders_with_paths = [f.path for f in os.scandir(image_dir) if f.is_dir()]
        max_workers = 4
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:

            def deploy_images_batch_helper(args_tuple: List[Any]) -> List[Tuple[str, str, str]]:
                return _deploy_images_batch(
                    path=args_tuple[0], image_name=args_tuple[1], env=args_tuple[2], build_execution_role=args_tuple[3]
                )

            args_tuples = [
                (path, path.split("/")[-1], env, codebuild_role)
                for path in list_subfolders_with_paths
                if "k8s-utilities" not in path
            ]

            results = list(executor.map(deploy_images_batch_helper, args_tuples))
            for res in results:
                im = str(res[0]).replace("-", "_")
                new_images_manifest[im] = ImageManifest(repository=str(res[1]), version=str(res[2]))
    _logger.debug(new_images_manifest)
    # Because this is multihreaded, we need to make sure we have the MOST UP TO DATE context
    # So, fetch it again and rewrite...
    context_latest: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
    context_latest.images = ImagesManifest(**new_images_manifest)  # type: ignore
    ContextSerDe.dump_context_to_ssm(context=context_latest)


def deploy_user_image(
    path: str, env: str, image_name: str, script: Optional[str], build_args: Optional[List[str]], timeout: int = 45
) -> None:
    _logger.debug(f"deploy_user_image args: {path} {env} {image_name} {script} {build_args} {timeout}")

    _logger.debug(build_args)
    _deploy_remote_image(
        path=path, env=env, image_name=image_name, script=script, build_args=build_args, timeout=timeout
    )


def deploy_credentials(env_name: str, ciphertext: str) -> None:
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("Context loaded.")

    @remotectl.remote_function("orbit", codebuild_role=context.toolkit.admin_role)
    def deploy_credentials(env_name: str, ciphertext: str) -> None:
        new_credentials = json.loads(kms.decrypt(context=context, ciphertext=ciphertext))
        secret_id = f"orbit-{env_name}-docker-credentials"
        existing_credentials = secretsmanager.get_secret_value(secret_id=secret_id)
        for registry, creds in new_credentials.items():
            username = creds.get("username", "")
            password = creds.get("password", "")
            try:
                subprocess.check_call(
                    f"docker login --username '{username}' --password '{password}' {registry}", shell=True
                )
            except Exception as e:
                _logger.error("Invalid Registry Credentials")
                _logger.exception(e)
                return
            else:
                existing_credentials = {**existing_credentials, **new_credentials}
        secretsmanager.put_secret_value(secret_id=secret_id, secret=existing_credentials)
        _logger.debug("Registry Credentials deployed")

    deploy_credentials(env_name=env_name, ciphertext=ciphertext)


def deploy_foundation(env_name: str) -> None:
    _logger.debug("env_name: %s", env_name)
    context: "FoundationContext" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=FoundationContext)
    _logger.debug("Context loaded.")

    @remotectl.remote_function("orbit", codebuild_role=context.toolkit.admin_role)
    def deploy_foundation(env_name: str) -> None:
        docker.login(context=context)
        _logger.debug("DockerHub and ECR Logged in")
        cdk_toolkit.deploy(context=context)
        _logger.debug("CDK Toolkit Stack deployed")
        foundation.deploy(context=context)
        _logger.debug("Demo Stack deployed")

    deploy_foundation(env_name=env_name)


def deploy_env(env_name: str, manifest_dir: str) -> None:
    _logger.debug("env_name: %s", env_name)
    manifest: Optional[Manifest] = ManifestSerDe.load_manifest_from_ssm(env_name=env_name, type=Manifest)
    _logger.debug("Manifest loaded.")
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("Context loaded.")
    changeset: Optional["Changeset"] = load_changeset_from_ssm(env_name=env_name)
    _logger.debug("Changeset loaded.")

    if manifest is None:
        raise Exception("Unable to load Manifest")

    @remotectl.remote_function(
        "orbit",
        codebuild_role=context.toolkit.admin_role,
        extra_dirs={
            "manifests": manifest_dir,
        },
    )
    def deploy_env(env_name: str, manifest_dir: str) -> None:
        docker.login(context=context)
        _logger.debug("DockerHub and ECR Logged in")
        cdk_toolkit.deploy(context=context)
        _logger.debug("CDK Toolkit Stack deployed")
        env.deploy(
            context=context,
            eks_system_masters_roles_changes=changeset.eks_system_masters_roles_changeset if changeset else None,
        )

        _logger.debug("Env Stack deployed")
        eksctl.deploy_env(
            context=context,
            changeset=changeset,
        )
        _logger.debug("EKS Environment Stack deployed")
        kubectl.deploy_env(context=context)
        _logger.debug("Kubernetes Environment components deployed")

        helm.deploy_env(context=context)
        _logger.debug("Helm Charts installed")

        k8s_context = utils.get_k8s_context(context=context)
        kubectl.fetch_kubectl_data(context=context, k8s_context=k8s_context)
        ContextSerDe.dump_context_to_ssm(context=context)
        _logger.debug("Updating userpool redirect")
        _update_userpool_client(context=context)
        _update_userpool(context=context)

    deploy_env(env_name=env_name, manifest_dir=manifest_dir)


def _update_userpool(context: Context) -> None:
    cognito_client = boto3_client("cognito-idp")

    function_arn = (
        f"arn:aws:lambda:{context.region}:{context.account_id}:function:orbit-{context.name}-post-authentication"
    )

    cognito_client.update_user_pool(
        UserPoolId=context.user_pool_id,
        LambdaConfig={"PostAuthentication": function_arn, "PostConfirmation": function_arn},
    )


def _update_userpool_client(context: Context) -> None:
    cognito = boto3_client("cognito-idp")
    cognito.update_user_pool_client(
        UserPoolId=context.user_pool_id,
        ClientId=context.user_pool_client_id,
        CallbackURLs=[
            f"{context.landing_page_url}/oauth2/idpresponse",
            f"{context.landing_page_url}/orbit/login",
            f"{context.landing_page_url}/saml2/idpresponse",
        ],
        LogoutURLs=[
            f"{context.landing_page_url}/orbit/logout",
        ],
        ExplicitAuthFlows=["ALLOW_CUSTOM_AUTH", "ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        SupportedIdentityProviders=["COGNITO"],
        AllowedOAuthFlows=["code"],
        AllowedOAuthScopes=["aws.cognito.signin.user.admin", "email", "openid", "profile"],
        AllowedOAuthFlowsUserPoolClient=True,
        PreventUserExistenceErrors="ENABLED",
        TokenValidityUnits={"AccessToken": "minutes", "IdToken": "minutes", "RefreshToken": "days"},
        RefreshTokenValidity=90,
        AccessTokenValidity=60,
        IdTokenValidity=60,
    )


def deploy_teams(env_name: str, manifest_dir: str) -> None:
    _logger.debug("env_name: %s", env_name)
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("Context loaded.")
    changeset: Optional["Changeset"] = load_changeset_from_ssm(env_name=env_name)
    _logger.debug("Changeset loaded.")

    @remotectl.remote_function(
        "orbit",
        codebuild_role=context.toolkit.admin_role,
        extra_dirs={
            "manifests": manifest_dir,
        },
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
    def deploy_teams(env_name: str, manifest_dir: str) -> None:
        if changeset:
            plugins.PLUGINS_REGISTRIES.load_plugins(
                context=context,
                plugin_changesets=changeset.plugin_changesets,
                teams_changeset=changeset.teams_changeset,
            )
            _logger.debug("Plugins loaded")

        docker.login(context=context)
        _logger.debug("DockerHub and ECR Logged in")
        if changeset and changeset.teams_changeset and changeset.teams_changeset.removed_teams_names:
            kubectl.write_kubeconfig(context=context)
            for team_name in changeset.teams_changeset.removed_teams_names:
                team_context: Optional["TeamContext"] = context.get_team_by_name(name=team_name)
                if team_context is None:
                    raise RuntimeError(f"TeamContext {team_name} not found!")
                _logger.debug("Destory all user namespaces for %s", team_context.name)
                sh.run(f"kubectl delete namespaces -l orbit/team={team_context.name},orbit/space=user --wait=true")
                _logger.debug("Destroying team %s", team_name)
                plugins.PLUGINS_REGISTRIES.destroy_team_plugins(context=context, team_context=team_context)
                _logger.debug("Team Plugins destroyed")
                helm.destroy_team(context=context, team_context=team_context)
                _logger.debug("Team Helm Charts uninstalled")
                kubectl.destroy_team(context=context, team_context=team_context)
                _logger.debug("Kubernetes Team components destroyed")
                eksctl.destroy_team(context=context, team_context=team_context)
                _logger.debug("EKS Team Stack destroyed")
                teams.destroy_team(context=context, team_context=team_context)
                _logger.debug("Team %s destroyed", team_name)
                context.remove_team_by_name(name=team_name)
                ContextSerDe.dump_context_to_ssm(context=context)

        team_names = [t.name for t in context.teams]
        if changeset and changeset.teams_changeset and changeset.teams_changeset.added_teams_names:
            team_names.extend(changeset.teams_changeset.added_teams_names)

        manifest: Optional["Manifest"] = ManifestSerDe.load_manifest_from_ssm(env_name=context.name, type=Manifest)
        if manifest is None:
            raise RuntimeError(f"Manifest {context.name} not found!")
        kubectl.write_kubeconfig(context=context)
        for team_name in team_names:
            team_manifest = manifest.get_team_by_name(name=team_name)
            if team_manifest is None:
                raise RuntimeError(f"TeamManifest {team_name} not found!")
            teams.deploy_team(context=context, manifest=manifest, team_manifest=team_manifest)
            _logger.debug("Team Stacks deployed")
            team_context = context.get_team_by_name(name=team_name)
            if team_context is None:
                raise RuntimeError(f"TeamContext {team_name} not found!")
            eksctl.deploy_team(context=context, team_context=team_context)
            _logger.debug("EKS Team Stack deployed")
            kubectl.deploy_team(context=context, team_context=team_context)
            _logger.debug("Kubernetes Team components deployed")
            helm.deploy_team(context=context, team_context=team_context)
            _logger.debug("Team Helm Charts installed")
            plugins.PLUGINS_REGISTRIES.deploy_team_plugins(
                context=context, team_context=team_context, changes=changeset.plugin_changesets if changeset else []
            )

            team_context.plugins = team_manifest.plugins
            ContextSerDe.dump_context_to_ssm(context=context)
            _logger.debug("Team Plugins deployed")

        _logger.debug("Teams deployed")

    deploy_teams(env_name=env_name, manifest_dir=manifest_dir)
