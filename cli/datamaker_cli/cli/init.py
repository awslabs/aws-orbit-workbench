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
from typing import Optional, Sequence

import click

from datamaker_cli.manifest import Manifest, SubnetKind, SubnetManifest, TeamManifest, VpcManifest
from datamaker_cli.spinner import start_spinner
from datamaker_cli.utils import get_region, stylize

_logger: logging.Logger = logging.getLogger(__name__)


def create_manifest(
    name: str, filename: str, teams_names: Sequence[str], demo: bool, images_from_source: bool, region: Optional[str]
) -> None:
    subnets = [
        SubnetManifest(subnet_id="PRIVATE_SUBNET_ID_PLACEHOLDER_A", kind=SubnetKind.private),
        SubnetManifest(subnet_id="PRIVATE_SUBNET_ID_PLACEHOLDER_B", kind=SubnetKind.private),
        SubnetManifest(subnet_id="PUBLIC_SUBNET_ID_PLACEHOLDER_A", kind=SubnetKind.public),
        SubnetManifest(subnet_id="PUBLIC_SUBNET_ID_PLACEHOLDER_B", kind=SubnetKind.public),
    ]
    vpc = VpcManifest(subnets=subnets)
    teams = [
        TeamManifest(
            name=team_name,
            env_name=name,
            instance_type="m5.4xlarge",
            local_storage_size=128,
            nodes_num_desired=2,
            nodes_num_max=3,
            nodes_num_min=1,
            policy="AdministratorAccess",
        )
        for team_name in teams_names
    ]
    manifest = Manifest(
        name=name,
        region=region if region is not None else get_region(),
        demo=demo,
        images_from_source=images_from_source,
        vpc=vpc,
        teams=teams,
    )
    manifest.write_file(filename=filename)


def init(name: str, team: Sequence[str], demo: bool, images_from_source: bool, region: Optional[str]) -> None:
    """Creates the DataMaker manifest file (yaml) where all your deployment settings will rest."""
    name = name.lower()
    filename: str = f"./{name}.yaml"
    with start_spinner(msg=f"Generating {filename}") as spinner:
        create_manifest(
            name=name,
            filename=filename,
            teams_names=team,
            demo=demo,
            images_from_source=images_from_source,
            region=region,
        )
        spinner.succeed()
        if demo:
            click.echo(message=(f"\nRecommended next step:\n\n" f"{stylize('>')} datamaker deploy -f {filename}\n"))
        else:
            click.echo(
                message=(
                    f"\nPlease, open the {stylize(filename)} file, "
                    f"fill up all {stylize('PLACEHOLDERS')}, adjust your {stylize('preferences')} "
                    f"and run:\n\n"
                    f"{stylize('>')} datamaker deploy -f {filename}\n"
                )
            )
