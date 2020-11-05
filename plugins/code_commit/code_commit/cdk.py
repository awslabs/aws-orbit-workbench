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
import sys

import aws_cdk.aws_codecommit as codecommit
from aws_cdk.core import App, Construct, Environment, Stack, Tags
from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest

_logger: logging.Logger = logging.getLogger(__name__)


class Team(Stack):
    def __init__(self, scope: Construct, id: str, manifest: Manifest, team_manifest: TeamManifest) -> None:
        self.scope = scope
        self.id = id
        self.manifest = manifest
        self.team_manifest = team_manifest
        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=self.manifest.account_id, region=self.manifest.region),
        )
        Tags.of(scope=self).add(key="Env", value=f"datamaker-{self.manifest.name}")
        self.repo: codecommit.Repository = self._create_repo()

    def _create_repo(self) -> codecommit.Repository:
        return codecommit.Repository(
            scope=self,
            id="repo",
            repository_name=f"datamaker-{self.manifest.name}-{self.team_manifest.name}",
        )


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 3:
        filename: str = sys.argv[1]
        team_name: str = sys.argv[2]
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    manifest: Manifest = Manifest(filename=filename)
    manifest.fillup()

    for team in manifest.teams:
        if team.name == team_name:
            team_manifest: TeamManifest = team
            break
    else:
        raise ValueError(f"Team {team_name} not found in the manifest.")

    stack_name = f"datamaker-{manifest.name}-{team_manifest.name}-codecommit"
    outdir = os.path.join(
        manifest.filename_dir,
        ".datamaker.out",
        manifest.name,
        "cdk",
        stack_name,
    )
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)

    app = App(outdir=outdir)
    Team(scope=app, id=stack_name, manifest=manifest, team_manifest=team_manifest)
    app.synth(force=True)


if __name__ == "__main__":
    main()
