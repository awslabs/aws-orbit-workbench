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

from datamaker_cli import bundle
from datamaker_cli.manifest import Manifest
from datamaker_cli.services import codebuild, s3

_logger: logging.Logger = logging.getLogger(__name__)


def _execute_codebuild(manifest: Manifest, command: str) -> None:
    bundle_location = f"{manifest.toolkit_s3_bucket}/cli/remote/{command}/bundle.zip"
    _logger.debug("bundle_location: %s", bundle_location)
    build_id = codebuild.start(
        project_name=manifest.toolkit_codebuild_project,
        bundle_location=bundle_location,
        spec=codebuild.generate_spec(
            pre_cmds=[],
            build_cmds=[f"datamaker remote --command {command}"],
            post_cmds=[],
            bundle_location=bundle_location,
        ),
        timeout=10,
    )
    codebuild.wait(build_id=build_id)


def execute_remote(filename: str, manifest: Manifest, command: str) -> None:
    bundle_path = bundle.generate_bundle(filename=filename)
    bucket = manifest.toolkit_s3_bucket
    key = f"cli/remote/{command}/bundle.zip"
    s3.delete_objects(bucket=bucket, keys=[key])
    s3.upload_file(
        src=bundle_path,
        bucket=bucket,
        key=key,
    )
    _execute_codebuild(manifest=manifest, command=command)
