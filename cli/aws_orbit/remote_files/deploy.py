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
from softwarelabs_remote_toolkit.services import cfn


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


def _deploy_image(args: Tuple[str, ...]) -> None:
    _logger.debug("_deploy_image args: %s", args)
    if len(args) < 4:
        raise ValueError("Unexpected number of values in args.")
    env: str = args[0]
    image_name: str = args[1]
    dir: str = args[2]
    script: Optional[str] = args[3] if args[3] != "NO_SCRIPT" else None
    build_args = args[4:]

    manifest = ManifestSerDe.load_manifest_from_ssm(env_name=env, type=Manifest)
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env, type=Context)
    _logger.debug("context: %s", vars(context))

    if manifest is None:
        raise Exception("Unable to load required Manifest from SSM")

    docker.login(context=context)
    _logger.debug("DockerHub and ECR Logged in")
    _logger.debug("Deploying the %s Docker image", image_name)

    ecr_repo = f"orbit-{context.name}/{image_name}"
    if not ecr.describe_repositories(repository_names=[ecr_repo]):
        ecr.create_repository(repository_name=ecr_repo, env_name=context.name)

    image_def: ImageManifest = getattr(manifest.images, image_name.replace("-", "_"))
    source = image_def.get_source(account_id=context.account_id, region=context.region)
    if source == "code":
        _logger.debug("Building and deploy docker image from source...")
        path = os.path.join(os.getcwd(), "bundle", dir)
        _logger.debug("path: %s", path)
        if script is not None:
            sh.run(f"sh {script}", cwd=path)
        tag = cast(str, image_def.version)
        docker.deploy_image_from_source(
            context=context,
            dir=path,
            name=ecr_repo,
            build_args=cast(Optional[List[str]], build_args),
            tag=tag,
        )
    else:
        _logger.debug("Replicating docker image to ECR...")
        docker.replicate_image(
            context=context,
            image_name=image_name,
            deployed_name=ecr_repo,
            source=source,
            source_repository=image_def.repository,
            source_version=image_def.version,
        )

    _logger.debug("Docker Image Deployed to ECR")


def _deploy_image_v2(image_name: str, env: str, build_args: Optional[List[str]]) -> None:
    region = get_region()
    account_id = get_account_id()
    _logger.debug(f"_deploy_image_v2 args: {account_id}, {region}, {image_name}, {env}")

    docker.login_v2(account_id=account_id, region=region)
    _logger.debug("DockerHub and ECR Logged in")
    _logger.debug("Deploying the %s Docker image", image_name)

    # ref = f"{account_id}.dkr.ecr.{region}.amazonaws.com/orbit/{image_name}"
    ecr_repo = f"orbit/{image_name}"
    if not ecr.describe_repositories(repository_names=[ecr_repo]):
        ecr.create_repository_v2(repository_name=ecr_repo)

    _logger.debug("Building and deploy docker image from source...")
    path = os.path.join(os.getcwd(), image_name)
    _logger.debug("path: %s", path)

    # if script is not None:
    # sh.run(f"sh {script}", cwd=path)
    # tag = cast(str, image_def.version)
    docker.deploy_image_from_source_v2(
        dir=path,
        name=ecr_repo,
        build_args=build_args,
        tag=env,
    )

    _logger.debug("Docker Image Deployed to ECR")


def _deploy_image_remotely(context: "Context", name: str, bundle_path: str, buildspec: codebuild.SPEC_TYPE) -> None:
    _logger.debug("Deploying %s Docker Image remotely into ECR", name)
    remote.run(
        command_name=f"deploy_image-{name}",
        context=context,
        bundle_path=bundle_path,
        buildspec=buildspec,
        codebuild_log_callback=None,
        timeout=30,
    )
    _logger.debug("%s Docker Image deployed into ECR", name)


def _deploy_images_batch(
    manifest: Manifest, context: "Context", images: List[Tuple[str, Optional[str], Optional[str], List[str]]]
) -> None:
    _logger.debug("images:\n%s", images)

    new_images_manifest = {name: getattr(context.images, name) for name in context.images.names}
    max_workers = 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: List[Future[Any]] = []
        name: str = ""
        dir: Optional[str] = None
        script: Optional[str] = None
        build_args: List[str] = []

        for name, dir, script, build_args in images:
            _logger.debug("name: %s | script: %s", name, script)

            path = os.path.join(os.getcwd(), "bundle", name)
            _logger.debug("path: %s", path)

            image_attr_name = name.replace("-", "_")
            image_def: ImageManifest = getattr(manifest.images, image_attr_name)
            tag = image_def.version
            if image_def.get_source(account_id=context.account_id, region=context.region) == "code":
                dirs: List[Tuple[str, str]] = [(path, cast(str, dir))]
            else:
                dirs = []

            bundle_path = bundle.generate_bundle(command_name=f"deploy_image-{name}", context=context, dirs=dirs)
            _logger.debug("bundle_path: %s", bundle_path)
            script_str = "NO_SCRIPT" if script is None else script
            build_args = [] if build_args is None else build_args
            buildspec = codebuild.generate_spec(
                context=context,
                plugins=False,
                cmds_build=[
                    "orbit remote --command _deploy_image "
                    f"{context.name} {name} {dir} {script_str} {' '.join(build_args)}"
                ],
            )
            new_images_manifest[image_attr_name] = ImageManifest(
                repository=f"{context.account_id}.dkr.ecr.{context.region}.amazonaws.com/orbit-{context.name}/{name}",
                version=tag,
                path=None,
            )
            futures.append(executor.submit(_deploy_image_remotely, context, name, bundle_path, buildspec))

        for f in futures:
            f.result()

        context.images = ImagesManifest(**new_images_manifest)
        ContextSerDe.dump_context_to_ssm(context=context)


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
    # t = resolve_parameters(helper, dict())
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
    return j  # type: ignore


def _deploy_images_batch_v2(
    path: str,
    image_name: str,
    env: str,
    build_args: List[str] = [],
) -> None:
    _logger.debug(f"_deploy_images_remotely_v2 args: {path} {image_name} {env}")
    # image_name = image_name.replace("-", "_")

    extra_dirs = {image_name: path}
    pre_build_commands = []
    if os.path.exists(os.path.join(path, "toolkit_helper.json")):
        f = os.path.join(path, "toolkit_helper.json")
        helper = _load_toolkit_helper(file_path=f, image_name=image_name, env=env)
        _logger.debug(helper)
        if helper.get("extra_dirs"):  # type: ignore
            extra_dirs = {**extra_dirs, **helper["extra_dirs"]}  # type: ignore
        if helper.get("build_args"):  # type: ignore
            build_args = [*build_args, *helper["build_args"]]  # type: ignore
        if helper.get("pre_build_commands"):  # type: ignore
            pre_build_commands = [*build_args, *helper["pre_build_commands"]]  # type: ignore
    else:
        _logger.debug("No Toolkit Helper")

    _logger.debug(f"extra_dirs: {extra_dirs}")
    _logger.debug(f"build_args: {build_args}")

    @remotectl.remote_function(
        "orbit",
        codebuild_role="Admin",
        extra_dirs=extra_dirs,
        bundle_id=image_name,
        extra_pre_build_commands=pre_build_commands,
    )
    def _deploy_images_batch_v2(path: str, image_name: str, env: str, build_args: List[str]) -> None:
        _logger.info(f"running ...{image_name} at {path}")
        _deploy_image_v2(image_name=image_name, env=env, build_args=build_args)

    _deploy_images_batch_v2(path, image_name, env, build_args)


def deploy_images_remotely_v2(env: str, requested_image: Optional[str] = None) -> None:
    _logger.debug(f"deploy_images_remotely_v2 args: {env} {requested_image}")
    image_dir = os.path.realpath(os.path.join(ORBIT_CLI_ROOT, "../../images"))

    if requested_image:
        if os.path.isdir(f"{image_dir}/{requested_image}"):
            _logger.debug(f"Request build of single image {requested_image}")
            _deploy_images_batch_v2(path=f"{image_dir}/{requested_image}", image_name=requested_image, env=env)
        else:
            _logger.error("An image was requested to be built, but it doesn't exist in the images/ dir")

    else:
        # first build k8s-utilities
        _deploy_images_batch_v2(path=f"{image_dir}/k8s-utilities", image_name="k8s-utilities", env=env)

        # now build the images dependent on k8s
        list_subfolders_with_paths = [f.path for f in os.scandir(image_dir) if f.is_dir()]
        for path in list_subfolders_with_paths:
            if "k8s-utilities" not in path:
                image = path.split("/")[-1]
                _deploy_images_batch_v2(path=path, image_name=image, env=env)


def deploy_images_remotely(manifest: Manifest, context: "Context", skip_images: bool = True) -> None:
    # Required images we always build/replicate
    images: List[Tuple[str, Optional[str], Optional[str], List[str]]] = []

    # This isn't obvious to read, but when skipping image builds, we intentionally remove these images if the source
    # is code. Otherwise, we build/deploy them
    if not (manifest.images.k8s_utilities.get_source(context.account_id, context.region) == "code" and skip_images):
        images.append(("k8s-utilities", "k8s-utilities", None, []))
    if not (manifest.images.orbit_controller.get_source(context.account_id, context.region) == "code" and skip_images):
        images.append(("orbit-controller", "orbit-controller", None, []))

    # Secondary images we can optionally skip
    if not skip_images:
        # When not skipping images, include these secondaries if their source isn't the default ecr-public
        if manifest.images.jupyter_user.get_source(context.account_id, context.region) != "ecr-public":
            images.append(("jupyter-user", "jupyter-user", "build.sh", []))

    _logger.debug("Building/repclicating Container Images")
    _deploy_images_batch(manifest=manifest, context=context, images=images)


def deploy_credentials(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    if len(args) != 2:
        raise ValueError("Unexpected number of values in args")
    env_name: str = args[0]
    ciphertext: str = args[1]
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("Context loaded.")

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
