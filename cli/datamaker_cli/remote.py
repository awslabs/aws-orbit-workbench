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
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from datamaker_cli import bundle
from datamaker_cli.manifest import Manifest
from datamaker_cli.services import cloudwatch, codebuild, s3

_logger: logging.Logger = logging.getLogger(__name__)


def _print_codebuild_logs(events: List[cloudwatch.CloudWatchEvent], progress_callback: Callable[[str], None]) -> None:
    for event in events:
        msg = event.message[:-1] if event.message.endswith("\n") else event.message
        _logger.debug("[CODEBUILD] %s", msg)
        progress_callback(msg)


def _execute_codebuild(manifest: Manifest, command: str, progress_callback: Callable[[str], None]) -> None:
    bundle_location = f"{manifest.toolkit_s3_bucket}/cli/remote/{command}/bundle.zip"
    _logger.debug("bundle_location: %s", bundle_location)
    stream_name_prefix = f"{command}-{int(datetime.now(timezone.utc).timestamp() * 1_000_000)}"
    _logger.debug("stream_name_prefix: %s", stream_name_prefix)
    build_id = codebuild.start(
        project_name=manifest.toolkit_codebuild_project,
        stream_name=stream_name_prefix,
        bundle_location=bundle_location,
        spec=codebuild.generate_spec(
            pre_cmds=[],
            build_cmds=[f"datamaker remote --command {command}"],
            post_cmds=[],
            bundle_location=bundle_location,
        ),
        timeout=10,
    )
    start_time: Optional[datetime] = None
    stream_name: Optional[str] = None
    for status in codebuild.wait(build_id=build_id):
        if status.logs.enabled and status.logs.group_name:
            if stream_name is None:
                stream_name = cloudwatch.get_stream_name_by_prefix(
                    group_name=status.logs.group_name, prefix=f"{stream_name_prefix}/"
                )
                _logger.debug("stream_name: %s", stream_name)
            if stream_name is not None:
                _logger.debug("start_time: %s", start_time)
                events = cloudwatch.get_log_events(
                    group_name=status.logs.group_name, stream_name=stream_name, start_time=start_time
                )
                _print_codebuild_logs(events=events.events, progress_callback=progress_callback)
                if events.last_timestamp is not None:
                    start_time = events.last_timestamp + timedelta(milliseconds=1)


def execute_remote(filename: str, manifest: Manifest, command: str, progress_callback: Callable[[str], None]) -> None:
    bundle_path = bundle.generate_bundle(filename=filename)
    bucket = manifest.toolkit_s3_bucket
    key = f"cli/remote/{command}/bundle.zip"
    s3.delete_objects(bucket=bucket, keys=[key])
    s3.upload_file(
        src=bundle_path,
        bucket=bucket,
        key=key,
    )
    time.sleep(3)  # Avoiding eventual consistence issues
    _execute_codebuild(manifest=manifest, command=command, progress_callback=progress_callback)
