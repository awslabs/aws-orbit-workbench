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
from typing import Optional, Tuple

import click

from datamaker_cli.commands.deploy import deploy
from datamaker_cli.commands.deploy_image import deploy_image
from datamaker_cli.commands.destroy import destroy
from datamaker_cli.commands.destroy_image import destroy_image
from datamaker_cli.commands.init import init
from datamaker_cli.commands.list import list_images

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
    """DataMaker CLI - Data & ML Unified Development and Production Environment"""
    pass


@click.command(name="init")
@click.option(
    "--name",
    "-n",
    type=str,
    help="The name of the DataMaker enviroment. MUST be unique per AWS account.",
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
    "--demo/--no-demo", default=True, help="Increment the deployment with demostration components.", show_default=True
)
@click.option(
    "--dev/--no-dev",
    default=True,
    help="Enable the development mode (docker images and packages build from source).",
    show_default=True,
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
    demo: bool,
    dev: bool,
    debug: bool,
) -> None:
    """Creates a DataMaker manifest model file (yaml) where all your deployment settings will rest."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    _logger.debug("name: %s", name)
    _logger.debug("region: %s", region)
    _logger.debug("demo: %s", demo)
    _logger.debug("dev: %s", dev)
    _logger.debug("debug: %s", debug)
    init(name=name, region=region, demo=demo, dev=dev, debug=debug)


@click.command(name="deploy")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target DataMaker manifest file (yaml).",
)
@click.option(
    "--username",
    "-u",
    type=str,
    help="Dockerhub username (Required only for the first deploy).",
)
@click.option(
    "--password",
    "-p",
    type=str,
    help="Dockerhub password (Required only for the first deploy).",
)
@click.option(
    "--skip-images/--no-skip-images",
    default=False,
    help="Skip Docker images updates (Usually for development purpose).",
    show_default=True,
)
@click.option("--env-stacks/--all-stacks", default=False, help="Deploy Environment Stacks only", show_default=True)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def deploy_cli(
    filename: str,
    skip_images: bool,
    env_stacks: bool,
    debug: bool,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """Deploy a DataMaker environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    _logger.debug("username: %s", username)
    _logger.debug("skip_images: %s", skip_images)
    deploy(
        filename=filename,
        username=username,
        password=password,
        skip_images=skip_images,
        env_only=env_stacks,
        debug=debug,
    )

@click.command(name="destroy")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target DataMaker manifest file (yaml).",
)
@click.option(
    "--team-stacks/--all-stacks", default=False, help="Destroy Team Stacks only or All Stacks", show_default=True
)
@click.option(
    "--keep-demo", default=False, help="Destroy Env and Team, but keeps Demo env if one was used", show_default=True
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def destroy_cli(filename: str,team_stacks: bool, keep_demo: bool, debug: bool) -> None:
    """Destroy a DataMaker environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    _logger.debug("teams only: %s", str(team_stacks))
    _logger.debug("keep demo: %s", str(keep_demo))
    destroy(filename=filename, teams_only=team_stacks, keep_demo=keep_demo, debug=debug)

@click.command(name="deploy-image")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target DataMaker manifest file (yaml).",
    show_default=False,
    required=True,
)
@click.option("--dir", "-d", type=str, help="Dockerfile directory.", required=True)
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
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def deploy_image_cli(filename: str, dir: str, name: str, script: Optional[str], debug: bool) -> None:
    """Build and Deploy a new Docker image into ECR."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    _logger.debug("dir: %s", dir)
    _logger.debug("name: %s", name)
    _logger.debug("script: %s", script)
    _logger.debug("debug: %s", debug)
    deploy_image(dir=dir, name=name, filename=filename, script=script, debug=debug)


@click.command(name="destroy-image")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target DataMaker manifest file (yaml).",
    show_default=False,
    required=True,
)
@click.option("--name", "-n", type=str, help="Image name.", required=True)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def destroy_image_cli(filename: str, name: str, debug: bool) -> None:
    """Destroy a Docker image from ECR."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    _logger.debug("name: %s", name)
    _logger.debug("debug: %s", debug)
    destroy_image(name=name, filename=filename, debug=debug)


@click.command(name="list-images")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target DataMaker manifest file (yaml).",
    show_default=False,
    required=True,
)
@click.option(
    "--debug/--no-debug",
    default=False,
    help="Enable detailed logging.",
    show_default=True,
)
def list_images_cli(filename: str, debug: bool) -> None:
    """List all Docker images available into the target environment."""
    if debug:
        enable_debug(format=DEBUG_LOGGING_FORMAT)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    list_images(filename=filename)


@click.command(name="remote", hidden=True)
@click.option(
    "--filename",
    "-f",
    default="./conf/manifest.yaml",
    type=str,
)
@click.option("--command", "-c", type=str, required=True)
@click.argument("args", nargs=-1)
def remote_cli(filename: str, command: str, args: Tuple[str]) -> None:
    """Run command remotely on CodeBuild"""
    enable_debug(format=DEBUG_LOGGING_FORMAT_REMOTE)
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    _logger.debug("command: %s", command)
    _logger.debug("args: %s", args)
    from datamaker_cli.remote_files import REMOTE_FUNC_TYPE, RemoteCommands

    remote_func: REMOTE_FUNC_TYPE = getattr(RemoteCommands, command)
    remote_func(filename, args)


def main() -> int:
    cli.add_command(init_cli)
    cli.add_command(deploy_cli)
    cli.add_command(destroy_cli)
    cli.add_command(remote_cli)
    cli.add_command(deploy_image_cli)
    cli.add_command(destroy_image_cli)
    cli.add_command(list_images_cli)
    cli()
    return 0
