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
from typing import TYPE_CHECKING, Dict, List, Optional, Union, cast

from datamaker_cli import sh
from datamaker_cli.remote_files.utils import get_k8s_context

if TYPE_CHECKING:
    from datamaker_cli.manifest import Manifest
    from datamaker_cli.messages import MessagesContext

_logger: logging.Logger = logging.getLogger(__name__)


CHANGESET_FILE_IMAGE_TYPE = Dict[str, Union[str, None]]


class ImageChangeset:
    def __init__(self, team_name: str, old_image: Optional[str], new_image: Optional[str]) -> None:
        self.team_name: str = team_name
        self.old_image: Optional[str] = old_image
        self.new_image: Optional[str] = new_image

    def asdict(self) -> CHANGESET_FILE_IMAGE_TYPE:
        return vars(self)


CHANGESET_FILE_TYPE = Dict[str, List[CHANGESET_FILE_IMAGE_TYPE]]


class Changeset:
    def __init__(self, image_changesets: Optional[List[ImageChangeset]] = None) -> None:
        self.image_changesets: List[ImageChangeset] = [] if image_changesets is None else image_changesets

    def asdict(self) -> CHANGESET_FILE_TYPE:
        return {"image_changesets": [i.asdict() for i in self.image_changesets]}

    def write_changeset_file(self, filename: str) -> None:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as file:
            json.dump(obj=self.asdict(), fp=file, indent=4, sort_keys=True)
        _logger.debug("Changeset file written: %s", filename)

    def process_images_changes(self, manifest: "Manifest") -> None:
        context: Optional[str] = None
        for change in self.image_changesets:
            _logger.debug(f"Processing change: {change.asdict()}")
            if change.old_image == change.new_image:
                _logger.debug("Skipping dummy change")
            if context is None:
                context = get_k8s_context(manifest=manifest)
                _logger.debug("kubectl context: %s", context)
            _logger.debug(f"warn: Image change detected: Restarting {change.team_name} JupyterHub")
            sh.run(f"kubectl rollout restart deployment jupyterhub --namespace {change.team_name} --context {context}")


def extract_changeset(manifest: "Manifest", ctx: "MessagesContext") -> Changeset:
    if manifest.raw_ssm is None:
        return Changeset()

    # Images check
    image_changesets: List[ImageChangeset] = []
    for team in manifest.teams:
        if team.raw_ssm is None:
            raise RuntimeError(f"Team {team.name} manifest raw_ssm attribute not filled.")
        old_image: Optional[str] = cast(Optional[str], team.raw_ssm.get("image"))
        _logger.debug("Inpecting Image Change for team %s: %s -> %s", team.name, old_image, team.image)
        if team.image != team.raw_ssm.get("image"):
            ctx.info(f"Image change detected for Team {team.name}: {old_image} -> {team.image}")
            changeset: ImageChangeset = ImageChangeset(team_name=team.name, old_image=old_image, new_image=team.image)
            image_changesets.append(changeset)

    return Changeset(image_changesets=image_changesets)


def _read_changeset_file(filename: str) -> CHANGESET_FILE_TYPE:
    _logger.debug("reading changeset file (%s)", filename)
    with open(filename, "r") as file:
        return cast(CHANGESET_FILE_TYPE, json.load(fp=file))


def read_changeset_file(filename: str) -> Changeset:
    raw: CHANGESET_FILE_TYPE = _read_changeset_file(filename=filename)
    return Changeset(
        image_changesets=[
            ImageChangeset(team_name=cast(str, i["team_name"]), old_image=i["old_image"], new_image=i["new_image"])
            for i in cast(List[CHANGESET_FILE_IMAGE_TYPE], raw.get("image_changesets", []))
        ]
    )
