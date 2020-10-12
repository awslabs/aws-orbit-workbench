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
from typing import Callable, Optional, Sequence

import click

from datamaker_cli.commands.deploy import deploy
from datamaker_cli.commands.destroy import destroy
from datamaker_cli.commands.init import init

DEBUG_LOGGING_FORMAT = "[%(asctime)s][%(name)s.%(funcName)s:%(lineno)d] %(message)s"
_logger: logging.Logger = logging.getLogger(__name__)


def enable_debug() -> None:
    logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s][%(name)s.%(funcName)s:%(lineno)d] %(message)s")
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
    required=True,
)
@click.option(
    "--team",
    "-t",
    type=str,
    multiple=True,
    default=[],
    help="Teams spaces names.",
    show_default=True,
)
@click.option(
    "--plugins",
    "-p",
    type=str,
    multiple=True,
    default=[],
    help="plugins names.",
    show_default=True,
)
@click.option(
    "--region",
    "-r",
    type=str,
    default=None,
    help="AWS Region name (e.g. us-east-1). If None, it will be infered.",
    show_default=False,
)
@click.option("--demo/--no-demo", default=False, help="Increment the deployment with demostration components.")
@click.option("--debug/--no-debug", default=False, help="Enable detailed logging.", show_default=True)
@click.option(
    "--dev/--no-dev", default=True, help="Enable the development mode (docker images and packeges build from source)."
)
def init_cli(
    name: str,
    team: Sequence[str],
    plugins: Sequence[str],
    region: Optional[str],
    demo: bool,
    debug: bool,
    dev: bool,
) -> None:
    """Creates the DataMaker manifest file (yaml) where all your deployment settings will rest."""
    if debug:
        enable_debug()
    _logger.debug("name: %s", name)
    _logger.debug("team: %s", team)
    _logger.debug("plugins: %s", plugins)
    _logger.debug("region: %s", region)
    _logger.debug("demo: %s", demo)
    _logger.debug("debug: %s", debug)
    _logger.debug("dev: %s", dev)
    init(name=name, teams=team, plugins=plugins, region=region, demo=demo, dev=dev, debug=debug)


@click.command(name="deploy")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target DataMaker manifest file (yaml).",
)
@click.option("--debug/--no-debug", default=False, help="Enable detailed logging.", show_default=True)
def deploy_cli(filename: str, debug: bool) -> None:
    """Deploy a DataMaker environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug()
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    deploy(filename=filename, debug=debug)


@click.command(name="destroy")
@click.option(
    "--filename",
    "-f",
    type=str,
    help="The target DataMaker manifest file (yaml).",
)
@click.option("--debug/--no-debug", default=False, help="Enable detailed logging.", show_default=True)
def destroy_cli(filename: str, debug: bool) -> None:
    """Destroy a DataMaker environment based on a manisfest file (yaml)."""
    if debug:
        enable_debug()
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    destroy(filename=filename, debug=debug)


@click.command(name="remote", hidden=True)
@click.option(
    "--filename",
    "-f",
    default="./manifest.yaml",
    type=str,
)
@click.option("--command", "-c", type=str, required=True)
def remote_cli(filename: str, command: str) -> None:
    """Run command remotely on CodeBuild"""
    enable_debug()
    filename = filename if filename[0] in (".", "/") else f"./{filename}"
    _logger.debug("filename: %s", filename)
    _logger.debug("command: %s", command)
    from datamaker_cli.remote_files import RemoteCommands

    remote_func: Callable[[str], None] = getattr(RemoteCommands, command)
    remote_func(filename)


def main() -> int:
    cli.add_command(init_cli)
    cli.add_command(deploy_cli)
    cli.add_command(destroy_cli)
    cli.add_command(remote_cli)
    cli()
    return 0
