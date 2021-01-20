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

import base64
import logging
import os
import pickle
import shutil
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Type, cast

from aws_orbit import cdk, changeset, sh
from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.services import cfn

if TYPE_CHECKING:
    from aws_cdk.core import Stack

_logger: logging.Logger = logging.getLogger(__name__)


def _serialize_parameters(parameters: Dict[str, Any]) -> str:
    pickled: bytes = pickle.dumps(obj=parameters)
    return base64.b64encode(pickled).decode("utf-8")


def _deserialize_parameters(parameters: str) -> Dict[str, Any]:
    data: bytes = base64.b64decode(parameters.encode("utf-8"))
    return cast(Dict[str, Any], pickle.loads(data))


def cdk_handler(stack_class: Type["Stack"]) -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 5:
        stack_name: str = sys.argv[1]
        filename: str = sys.argv[2]
        team_name: str = sys.argv[3]
        parameters: Dict[str, Any] = _deserialize_parameters(parameters=sys.argv[4])
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    manifest: Manifest = Manifest(filename=filename, env=None, region=None)
    manifest.fillup()

    changes: changeset.Changeset = changeset.read_changeset_file(manifest=manifest, filename="changeset.json")
    if changes.teams_changeset and team_name in changes.teams_changeset.removed_teams_names:
        for team in changes.teams_changeset.old_teams:
            if team.name == team_name:
                team_manifest: TeamManifest = team
                team_manifest.fetch_ssm()
                break
        else:
            raise ValueError(f"Team {team_name} not found in the teams_changeset.old_teams list.")
    else:
        for team in manifest.teams:
            if team.name == team_name:
                team_manifest = team
                break
        else:
            raise ValueError(f"Team {team_name} not found in the manifest.")

    outdir = os.path.join(
        manifest.filename_dir,
        ".orbit.out",
        manifest.name,
        "cdk",
        stack_name,
    )
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)

    # Can't be imported globally because we only have CDK installed on CodeBuild
    from aws_cdk.core import App

    app = App(outdir=outdir)
    stack_class(app, stack_name, manifest, team_manifest, parameters)  # type: ignore
    app.synth(force=True)


def cdk_deploy(
    stack_name: str,
    app_filename: str,
    manifest: "Manifest",
    team_manifest: "TeamManifest",
    parameters: Dict[str, Any],
) -> None:
    if manifest.cdk_toolkit_stack_name is None:
        raise ValueError(f"manifest.cdk_toolkit_stack_name: {manifest.cdk_toolkit_stack_name}")
    args: List[str] = [stack_name, manifest.filename, team_manifest.name, _serialize_parameters(parameters=parameters)]
    cmd: str = (
        "cdk deploy --require-approval never --progress events "
        f"--toolkit-stack-name {manifest.cdk_toolkit_stack_name} "
        f"{cdk.get_app_argument(app_filename, args)} "
        f"{cdk.get_output_argument(manifest, stack_name)}"
    )
    sh.run(cmd=cmd)


def cdk_destroy(
    stack_name: str,
    app_filename: str,
    manifest: "Manifest",
    team_manifest: "TeamManifest",
    parameters: Dict[str, Any],
) -> None:
    if cfn.does_stack_exist(manifest=manifest, stack_name=stack_name) is False:
        _logger.debug("Skipping CDK destroy for %s, because the stack was not found.", stack_name)
        return
    if manifest.cdk_toolkit_stack_name is None:
        raise ValueError(f"manifest.cdk_toolkit_stack_name: {manifest.cdk_toolkit_stack_name}")
    args: List[str] = [stack_name, manifest.filename, team_manifest.name, _serialize_parameters(parameters=parameters)]
    cmd: str = (
        "cdk destroy --force "
        f"--toolkit-stack-name {manifest.cdk_toolkit_stack_name} "
        f"{cdk.get_app_argument(app_filename, args)} "
        f"{cdk.get_output_argument(manifest, stack_name)}"
    )
    sh.run(cmd=cmd)
