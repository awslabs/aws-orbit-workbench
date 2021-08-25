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

import json
import logging
import os
import sys
from typing import List, Optional, TextIO, Tuple, cast

import click

from aws_orbit.commands import deploy as deploy_commands
from aws_orbit.commands import destroy as destroy_commands
from aws_orbit.commands.build import build_image, build_podsetting
from aws_orbit.commands.delete import delete_image, delete_podsetting
from aws_orbit.commands.image import build_profile, delete_profile, list_profiles
from aws_orbit.commands.init import init
from aws_orbit.commands.list import list_env, list_images
from aws_orbit.utils import print_dir

DEBUG_LOGGING_FORMAT = "[%(asctime)s][%(filename)-13s:%(lineno)3d] %(message)s"
DEBUG_LOGGING_FORMAT_REMOTE = "[%(filename)-13s:%(lineno)3d] %(message)s"
_logger: logging.Logger = logging.getLogger(__name__)


def enable_debug(format: str) -> None:
    logging.basicConfig(level=logging.DEBUG, format=format)
    _logger.setLevel(logging.DEBUG)
    logging.getLogger("boto3").setLevel(logging.ERROR)
    logging.getLogger("botocore").setLevel(logging.ERROR)
    logging.getLogger("s3transfer").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("sh").setLevel(logging.ERROR)
    logging.getLogger("kubernetes").setLevel(logging.ERROR)


@click.group()
def cli() -> None:
    """Orbit Workbench CLI - Data & ML Unified Development and Production Environment"""
    pass


@click.command(name="init")
@click.option(
    "--name",
    "-n",
    type=str,
    help="The name of the Orbit Workbench enviroment. MUST be unique per AWS account.",
    required=False,
    default="my-env",
    show_default=True,
)
@click.option(
    "--region",
    "-r",
    type=str,
    default=None,
    help="AWS Region name (e.g. us-east-1). If None, it will be infered.",
    show_default=False,
    required=False,
)
@click.option(
    "--foundation/--no-foundation", default=True, help="Create Orbit foundation default manifest.", show_default=True
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def init_cli(
    name: str,
    region: Optional[str],
    foundation: bool,
    debug: bool,
) -> None:
    """Creates a Orbit Workbench manifest model file (yaml) where all your deployment settings will rest."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("name: %s", name)
    _logger.debug("region: %s", region)
    _logger.debug("foundation: %s", foundation)
    _logger.debug("debug: %s", debug)
    init(name=name, region=region, foundation=foundation, debug=debug)


@click.group(name="deploy")
def deploy() -> None:
    """Deploy foundation,env,teams in your Orbit Workbench."""
    pass


@deploy.command(name="toolkit")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target Orbit Workbench manifest file (yaml).",
    required=True,
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def deploy_toolkit(
    filename: str,
    debug: bool,
) -> None:
    """Deploy a Orbit Workbench environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    deploy_commands.deploy_toolkit(
        filename=filename,
        debug=debug,
    )


@deploy.command(name="credentials")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target Orbit Workbench manifest file (yaml).",
)
@click.option("--username", "-u", type=str, help="Image Registry username", required=True)
@click.option(
    "--password",
    "-p",
    type=str,
    help="Image Registry password",
)
@click.option("--registry", "-r", type=str, help="Image Registry name/URL", default="docker.io")
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def deploy_credentials(
    filename: str,
    username: str,
    password: str,
    registry: str,
    debug: bool,
) -> None:
    """Deploy Image Registry credentials for use in building and pulling images"""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("filename: %s", filename)
    _logger.debug("username: %s", username)
    _logger.debug("registry: %s", registry)
    deploy_commands.deploy_credentials(
        filename=filename,
        username=username,
        password=password,
        registry=registry,
        debug=debug,
    )


@deploy.command(name="teams")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target Orbit Workbench manifest file (yaml).",
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def deploy_teams(
    filename: str,
    debug: bool,
) -> None:
    """Deploy a Orbit Workbench environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    deploy_commands.deploy_teams(
        filename=filename,
        debug=debug,
    )


@deploy.command(name="env")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target Orbit Workbench manifest file (yaml).",
    required=True,
)
@click.option(
    "--skip-images/--build-images",
    default=True,
    help="Skip Docker images updates (Usually for development purpose).",
    show_default=True,
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def deploy_env(
    filename: str,
    skip_images: bool,
    debug: bool,
) -> None:
    """Deploy a Orbit Workbench environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    _logger.debug("skip_images: %s", skip_images)
    deploy_commands.deploy_env(
        filename=filename,
        skip_images=skip_images,
        debug=debug,
    )


@deploy.command(name="foundation")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target Orbit Workbench manifest file (yaml).",
)
@click.option(
    "--name",
    "-n",
    type=str,
    help="The Name of the Orbit Foundation deployment",
)
@click.option(
    "--codeartifact-domain",
    type=str,
    help="CodeArtifact Domain to pull packages from.",
)
@click.option(
    "--codeartifact-repository",
    type=str,
    help="CodeArtifact Repository to pull packages from.",
)
@click.option(
    "--ssl-cert-arn",
    type=str,
    help="SSL Certificate to integrate the ALB with.",
)
@click.option(
    "--custom-domain-name",
    type=str,
    help="The Custom Domain Name to associate the orbit framework with",
)
@click.option(
    "--internet-accessibility/--no-internet-accessibility",
    default=True,
    help="Configure for deployment to Private (internet accessibility) "
    "or Isolated (no internet accessibility) subnets.",
    show_default=True,
)
@click.option(
    "--max-availability-zones",
    default=2,
    help="The maximum number of Availability Zones to attempt to deploy in the VPC",
    show_default=True,
    type=int,
    required=False,
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def deploy_foundation(
    filename: Optional[str] = None,
    name: Optional[str] = None,
    debug: bool = False,
    internet_accessibility: bool = True,
    codeartifact_domain: Optional[str] = None,
    codeartifact_repository: Optional[str] = None,
    ssl_cert_arn: Optional[str] = None,
    custom_domain_name: Optional[str] = None,
    max_availability_zones: Optional[int] = None,
) -> None:
    """Deploy a Orbit Workbench foundation based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)

    if not filename and not name:
        raise click.ClickException('One of "filename" or "name" is required.')

    if filename:
        filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    _logger.debug("name: %s", name)
    _logger.debug("codeartifact_domain: %s", codeartifact_domain)
    _logger.debug("codeartifact_repository: %s", codeartifact_repository)
    _logger.debug("ssl_cert_arn: %s", ssl_cert_arn)
    _logger.debug("custom_domain_name: %s", custom_domain_name)
    _logger.debug("max_availability_zones: %s", max_availability_zones)
    deploy_commands.deploy_foundation(
        filename=filename,
        name=name,
        codeartifact_domain=codeartifact_domain,
        codeartifact_repository=codeartifact_repository,
        ssl_cert_arn=ssl_cert_arn,
        custom_domain_name=custom_domain_name,
        debug=debug,
        internet_accessibility=internet_accessibility,
        max_availability_zones=max_availability_zones,
    )


@click.group(name="destroy")
def destroy() -> None:
    """Destroy foundation,env,etc in your Orbit Workbench."""
    pass


@destroy.command(name="teams")
@click.option("--env", "-e", type=str, required=True, help="Destroy Orbit Teams.")
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def destroy_teams(env: str, debug: bool) -> None:
    """Destroy a Orbit Workbench environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    destroy_commands.destroy_teams(env=env, debug=debug)


@destroy.command(name="env")
@click.option("--env", "-e", type=str, required=True, help="Destroy Orbit Environment.")
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def destroy_env(env: str, debug: bool) -> None:
    """Destroy a Orbit Workbench environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    destroy_commands.destroy_env(env=env, debug=debug)


@destroy.command(name="foundation")
@click.option("--name", "-n", type=str, required=True, help="Destroy Orbit Foundation.")
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def destroy_foundation(name: str, debug: bool) -> None:
    """Destroy a Orbit Workbench environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("name: %s", name)
    destroy_commands.destroy_foundation(env=name, debug=debug)


@destroy.command(name="credentials")
@click.option("--env", "-e", type=str, required=True, help="Destroy Registry Credentials.")
@click.option("--registry", "-r", type=str, required=True, help="Image Registry.")
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def destroy_credentials(env: str, registry: str, debug: bool) -> None:
    """Destroy Image Registry Credentials previously stored"""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    _logger.debug("registry: %s", registry)
    destroy_commands.destroy_credentials(env=env, registry=registry, debug=debug)


@click.group(name="build")
def build() -> None:
    """Build images,profiles,etc in your Orbit Workbench."""
    pass


@build.command(name="image")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment.")
@click.option("--dir", "-d", type=str, help="Dockerfile directory.", required=True)
@click.option("--name", "-n", type=str, help="Image name.", required=True)
@click.option("--timeout", type=int, help="CodeBuild Timeout", default=30, show_default=True)
@click.option(
    "--script",
    "-s",
    type=str,
    default=None,
    help="Build script to run before the image build.",
    required=False,
)
@click.option(
    "--build-arg",
    type=str,
    multiple=True,
    default=[],
    help="One or more --build-arg parameters to pass to the Docker build command.",
    required=False,
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def deploy_image_cli(
    env: str,
    dir: str,
    name: str,
    timeout: Optional[int],
    script: Optional[str],
    build_arg: Optional[List[str]],
    debug: bool,
) -> None:
    """Build and Deploy a new Docker image into ECR."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    _logger.debug("dir: %s", dir)
    _logger.debug("name: %s", name)
    _logger.debug("script: %s", script)
    _logger.debug("timeout: %s", timeout)
    _logger.debug("debug: %s", debug)
    build_image(
        dir=dir, name=name, env=env, timeout=cast(int, timeout), script=script, build_args=build_arg, debug=debug
    )


@click.group(name="replicate")
def replicate() -> None:
    """Replicate images from external respositories into ECR"""
    pass


@replicate.command(name="image")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment.")
@click.option("--name", "-n", type=str, help="Image name.", required=True)
@click.option(
    "--script",
    "-s",
    type=str,
    default=None,
    help="Build script to run before the image build.",
    required=False,
)
@click.option(
    "--source-registry",
    "-y",
    type=str,
    multiple=False,
    default=None,
    help="One or more Teams to deploy the image to (can de declared multiple times).",
    required=True,
)
@click.option(
    "--source-repository",
    "-r",
    type=str,
    multiple=False,
    default=None,
    help="One or more Teams to deploy the image to (can de declared multiple times).",
    required=True,
)
@click.option(
    "--source-version",
    "-v",
    type=str,
    multiple=False,
    default=None,
    help="One or more Teams to deploy the image to (can de declared multiple times).",
    required=True,
)
@click.option(
    "--build-arg",
    type=str,
    multiple=True,
    default=[],
    help="One or more --build-arg parameters to pass to the Docker build command.",
    required=False,
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def replicate_image_cli(
    env: str,
    name: str,
    script: Optional[str],
    source_registry: str,
    source_repository: str,
    source_version: str,
    build_arg: Optional[List[str]],
    debug: bool,
) -> None:
    """Build and Deploy a new Docker image into ECR."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    _logger.debug("name: %s", name)
    _logger.debug("script: %s", script)
    _logger.debug("debug: %s", debug)
    build_image(
        dir=None,
        name=name,
        env=env,
        script=script,
        source_registry=source_registry,
        source_repository=source_repository,
        source_version=source_version,
        build_args=build_arg,
        debug=debug,
    )


@build.command(name="profile")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment.")
@click.option("--team", "-t", type=str, help="Orbit Team.", required=True)
@click.argument("profile", type=click.File("r"))
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def add_profile_cli(env: str, team: str, debug: bool, profile: TextIO) -> None:
    """Build and Deploy a new Docker image into ECR."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    _logger.debug("team: %s", team)
    profile_str = profile.read()
    _logger.debug("profile: %s", profile_str)
    _logger.debug("debug: %s", debug)
    build_profile(env=env, team=team, profile=profile_str, debug=debug)


@build.command(name="podsetting")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment.")
@click.option("--team", "-t", type=str, required=True, help="Orbit Team.")
@click.argument("podsetting", type=click.File("r"))
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def add_podsetting_cli(env: str, team: str, debug: bool, podsetting: TextIO) -> None:
    """Deploy a new podsetting to the K8s cluster."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    _logger.debug("team: %s", team)
    podsetting_str = podsetting.read()
    _logger.debug("podsetting: %s", podsetting_str)
    _logger.debug("debug: %s", debug)
    try:
        build_podsetting(env_name=env, team_name=team, podsetting=podsetting_str, debug=debug)
    except ImportError:
        raise click.ClickException('The "utils" submodule is required to use "run" commands')


@click.group(name="delete")
def delete() -> None:
    """Delete images,profiles,etc in your Orbit Workbench."""
    pass


@delete.command(name="profile")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment.")
@click.option("--team", "-t", type=str, help="Orbit Team.", required=True)
@click.option("--profile", "-p", type=str, help="Profile name to delete", required=True)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def delete_profile_cli(env: str, team: str, profile: str, debug: bool) -> None:
    """Build and Deploy a new Docker image into ECR."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    _logger.debug("team: %s", team)
    _logger.debug("profile: %s", profile)
    _logger.debug("debug: %s", debug)
    delete_profile(env=env, team=team, profile_name=profile, debug=debug)


@delete.command(name="podsetting")
@click.option("--team", "-t", type=str, help="Orbit Team.", required=True)
@click.option("--podsetting", "-n", type=str, help="Podsetting name to delete", required=True)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def delete_podsetting_cli(team: str, podsetting: str, debug: bool) -> None:
    """Delete a podsetting"""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("team: %s", team)
    _logger.debug("podsetting: %s", podsetting)
    _logger.debug("debug: %s", debug)
    delete_podsetting(namespace=team, podsetting_name=podsetting, debug=debug)


@delete.command(name="image")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment.")
@click.option("--name", "-n", type=str, help="Image name.", required=True)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def delete_image_cli(env: str, name: str, debug: bool) -> None:
    """Destroy a Docker image from ECR."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    _logger.debug("name: %s", name)
    _logger.debug("debug: %s", debug)
    delete_image(name=name, env=env, debug=debug)


@click.group(name="list")
def list() -> None:
    """List images,profiles,etc in your Orbit Workbench."""
    pass


@list.command(name="profile")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment.")
@click.option("--team", "-t", type=str, help="Orbit Team.", required=True)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def list_profiles_cli(env: str, team: str, debug: bool) -> None:
    """Build and Deploy a new Docker image into ECR."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("env: %s", env)
    _logger.debug("team: %s", team)
    _logger.debug("debug: %s", debug)
    list_profiles(env=env, team=team, debug=debug)


@list.command(name="image")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment.")
@click.option(
    "--region",
    "-r",
    type=str,
    default=None,
    help="AWS Region name (e.g. us-east-1). If None, it will be infered.",
    show_default=False,
    required=False,
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def list_images_cli(env: str, region: Optional[str], debug: bool) -> None:
    """List all Docker images available into the target environment."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    list_images(env=env, region=region)


@list.command(name="env")
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
@click.option("--env", "-e", type=str, required=False, default="", help="Select a single Orbit environment")
@click.option(
    "--variable",
    type=click.Choice(["all", "landing-page", "teams", "toolkitbucket"], case_sensitive=False),
    show_default=True,
    default="all",
)
def list_env_cli(debug: bool, env: str, variable: str) -> None:
    """List all Docker images available into the target environment."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    list_env(env, variable)


@click.command(name="remote", hidden=True)
@click.option("--command", "-c", type=str, required=True)
@click.argument("args", nargs=-1)
def remote_cli(command: str, args: Tuple[str]) -> None:
    """Run command remotely on CodeBuild"""
    enable_debug(format=DEBUG_LOGGING_FORMAT_REMOTE)
    from aws_orbit.remote_files import REMOTE_FUNC_TYPE, RemoteCommands

    _logger.debug("Remote bundle structure:")
    print_dir(os.getcwd(), exclude=["__pycache__", "cdk", ".venv", ".mypy_cache"])
    remote_func: REMOTE_FUNC_TYPE = getattr(RemoteCommands, command)
    remote_func(args)


@click.group(name="run")
def run_container() -> None:
    """Execute containers in the Orbit environment"""
    try:
        import aws_orbit_sdk  # noqa: F401
    except ImportError:
        raise click.ClickException('The "utils" submodule is required to use "run" commands')
    pass


@run_container.command(name="python", help="Run python script in a container")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment to execute container in.")
@click.option("--team", "-t", type=str, required=True, help="Orbit Team Space to execute container in.")
@click.option(
    "--user", "-u", type=str, default="jovyan", show_default=True, help="Jupyter user to execute container as."
)
@click.option("--wait/--no-wait", type=bool, default=False, show_default=True, help="Wait for execution to complete.")
@click.option(
    "--delay",
    type=int,
    required=False,
    help="If --wait, this is the number of seconds to sleep between container state checks.",
)
@click.option(
    "--max-attempts",
    type=int,
    required=False,
    help="If --wait, this is the number of times to check container state before failing.",
)
@click.option(
    "--tail-logs/--no-tail-logs",
    type=bool,
    default=False,
    show_default=True,
    help="If --wait, print a tail of container logs after execution completes.",
)
@click.option(
    "--debug/--no-debug",
    default=False,
    show_default=True,
    help="Enable detailed logging.",
)
@click.argument("input", type=click.File("r"))
def run_python_container(
    env: str,
    team: str,
    user: str,
    wait: bool,
    delay: Optional[int],
    max_attempts: Optional[int],
    tail_logs: bool,
    debug: bool,
    input: TextIO,
) -> None:
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)

    _logger.debug("env: %s", env)
    _logger.debug("team: %s", team)
    _logger.debug("user: %s", user)

    tasks = json.load(input)
    _logger.debug("tasks: %s", json.dumps(tasks))

    import aws_orbit.commands.run as run

    no_error_flag = run.run_python_container(
        env=env,
        team=team,
        user=user,
        tasks=tasks,
        wait=wait,
        delay=delay,
        max_attempts=max_attempts,
        tail_logs=tail_logs,
        debug=debug,
    )
    if no_error_flag:
        sys.exit(0)
    else:
        sys.exit(1)


@run_container.command(name="notebook", help="Run notebook in a container")
@click.option("--env", "-e", type=str, required=True, help="Orbit Environment to execute container in.")
@click.option("--team", "-t", type=str, required=True, help="Orbit Team Space to execute container in.")
@click.option(
    "--user", "-u", type=str, default="jovyan", show_default=True, help="Jupyter user to execute container as."
)
@click.option("--wait/--no-wait", type=bool, default=False, show_default=True, help="Wait for execution to complete.")
@click.option(
    "--delay",
    type=int,
    required=False,
    help="If --wait, this is the number of seconds to sleep between container state checks.",
)
@click.option(
    "--max-attempts",
    type=int,
    required=False,
    help="If --wait, this is the number of times to check container state before failing.",
)
@click.option(
    "--tail-logs/--no-tail-logs",
    type=bool,
    default=False,
    show_default=True,
    help="If --wait, print a tail of container logs after execution completes.",
)
@click.option(
    "--debug/--no-debug",
    default=False,
    show_default=True,
    help="Enable detailed logging.",
)
@click.argument("input", type=click.File("r"))
def run_notebook_container(
    env: str,
    team: str,
    user: str,
    wait: bool,
    delay: Optional[int],
    max_attempts: Optional[int],
    tail_logs: bool,
    debug: bool,
    input: TextIO,
) -> None:
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)

    _logger.debug("env: %s", env)
    _logger.debug("team: %s", team)
    _logger.debug("user: %s", user)

    tasks = json.load(input)
    _logger.debug("tasks: %s", json.dumps(tasks))

    import aws_orbit.commands.run as run

    no_error_flag = run.run_notebook_container(
        env=env,
        team=team,
        user=user,
        tasks=tasks,
        wait=wait,
        delay=delay,
        max_attempts=max_attempts,
        tail_logs=tail_logs,
        debug=debug,
    )
    if no_error_flag:
        sys.exit(0)
    else:
        sys.exit(1)


def main() -> int:
    # For now , we will not support init command and the deploy page points to manifest examples to be used.
    # cli.add_command(init_cli)
    cli.add_command(deploy)
    cli.add_command(destroy)
    cli.add_command(remote_cli)
    cli.add_command(run_container)
    cli.add_command(build)
    cli.add_command(delete)
    cli.add_command(list)
    cli.add_command(replicate)
    cli()
    return 0
