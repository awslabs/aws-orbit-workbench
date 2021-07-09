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

from aws_orbit import bundle, docker, plugins, remote, sh
from aws_orbit.models.changeset import Changeset, load_changeset_from_ssm
from aws_orbit.models.context import Context, ContextSerDe, FoundationContext, TeamContext
from aws_orbit.models.manifest import ImageManifest, ImagesManifest, Manifest, ManifestSerDe
from aws_orbit.remote_files import cdk_toolkit, eksctl, env, foundation, helm, kubectl, teams, utils
from aws_orbit.services import codebuild, ecr, kms, secretsmanager
from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


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


def deploy_foundation(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    if len(args) != 1:
        raise ValueError("Unexpected number of values in args")
    env_name: str = args[0]
    context: "FoundationContext" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=FoundationContext)
    _logger.debug("Context loaded.")
    docker.login(context=context)
    _logger.debug("DockerHub and ECR Logged in")
    cdk_toolkit.deploy(context=context)
    _logger.debug("CDK Toolkit Stack deployed")
    foundation.deploy(context=context)
    _logger.debug("Demo Stack deployed")


def deploy_env(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    if len(args) == 2:
        env_name: str = args[0]
        skip_images_remote_flag: str = str(args[1])
    else:
        raise ValueError("Unexpected number of values in args")

    manifest: Optional[Manifest] = ManifestSerDe.load_manifest_from_ssm(env_name=env_name, type=Manifest)
    _logger.debug("Manifest loaded.")
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("Context loaded.")
    changeset: Optional["Changeset"] = load_changeset_from_ssm(env_name=env_name)
    _logger.debug("Changeset loaded.")

    if manifest is None:
        raise Exception("Unable to load Manifest")

    docker.login(context=context)
    _logger.debug("DockerHub and ECR Logged in")
    cdk_toolkit.deploy(context=context)
    _logger.debug("CDK Toolkit Stack deployed")
    env.deploy(
        context=context,
        eks_system_masters_roles_changes=changeset.eks_system_masters_roles_changeset if changeset else None,
    )

    _logger.debug("Env Stack deployed")
    deploy_images_remotely(manifest=manifest, context=context, skip_images=skip_images_remote_flag == "skip-images")
    _logger.debug("Docker Images deployed")
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


def _update_userpool(context: Context) -> None:
    cognito_client = boto3_client("cognito-idp")

    function_arn = (
        f"arn:aws:lambda:{context.region}:{context.account_id}:function:orbit-{context.name}-post-authentication"
    )

    cognito_client.update_user_pool(UserPoolId=context.user_pool_id, LambdaConfig={"PostAuthentication": function_arn})


def _update_userpool_client(context: Context) -> None:
    cognito = boto3_client("cognito-idp")
    cognito.update_user_pool_client(
        UserPoolId=context.user_pool_id,
        ClientId=context.user_pool_client_id,
        CallbackURLs=[
            f"{context.landing_page_url}/oauth2/idpresponse",
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


def deploy_teams(args: Tuple[str, ...]) -> None:
    _logger.debug("args: %s", args)
    if len(args) == 1:
        env_name: str = args[0]
    else:
        raise ValueError("Unexpected number of values in args")

    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=env_name, type=Context)
    _logger.debug("Context loaded.")
    changeset: Optional["Changeset"] = load_changeset_from_ssm(env_name=env_name)
    _logger.debug("Changeset loaded.")

    if changeset:
        plugins.PLUGINS_REGISTRIES.load_plugins(
            context=context, plugin_changesets=changeset.plugin_changesets, teams_changeset=changeset.teams_changeset
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
