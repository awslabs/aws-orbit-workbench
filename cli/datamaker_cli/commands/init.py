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
from typing import Optional

from datamaker_cli.manifest import Manifest, PluginManifest, SubnetKind, SubnetManifest, TeamManifest, VpcManifest
from datamaker_cli.messages import MessagesContext, stylize
from datamaker_cli.utils import get_region

_logger: logging.Logger = logging.getLogger(__name__)


def create_manifest(
    name: str,
    filename: str,
    region: Optional[str],
    demo: bool,
    dev: bool,
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
            name="my-team",
            env_name=name,
            instance_type="m5.4xlarge",
            local_storage_size=128,
            nodes_num_desired=2,
            nodes_num_max=3,
            nodes_num_min=1,
            policy="AdministratorAccess",
        )
    ]
    manifest = Manifest(
        name=name,
        filename=filename,
        region=region if region is not None else get_region(),
        demo=demo,
        dev=dev,
        vpc=vpc,
        teams=teams,
        plugins=[PluginManifest(name="hello_world", path="plugins/hello_world/")],
    )
    manifest.write_file(filename=filename)


def init(name: str, region: Optional[str], demo: bool, dev: bool, debug: bool) -> None:
    """Creates the DataMaker manifest file (yaml) where all your deployment settings will rest."""
    with MessagesContext("Initializing", debug=debug) as ctx:
        name = name.lower()
        filename: str = f"./{name}.yaml"
        create_manifest(name=name, filename=filename, demo=demo, dev=dev, region=region)
        ctx.info(f"Manifest generated as {filename}")
        ctx.progress(100)
        if demo:
            ctx.tip(f"Recommended next step: {stylize(f'datamaker deploy -f {filename}')}")
        else:
            ctx.tip(
                f"Fill up all {stylize('PLACEHOLDERS', underline=True)} into {filename} "
                f"and run: "
                f"{stylize(f'datamaker deploy -f {filename}')}"
            )
