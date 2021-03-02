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
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from aws_orbit.models.context import Context
from aws_orbit.services import cloudwatch, codebuild, s3

_logger: logging.Logger = logging.getLogger(__name__)


def _print_codebuild_logs(
    events: List[cloudwatch.CloudWatchEvent],
    codebuild_log_callback: Callable[[str], None],
) -> None:
    for event in events:
        msg = event.message[:-1] if event.message.endswith("\n") else event.message
        _logger.debug("[CODEBUILD] %s", msg)
        codebuild_log_callback(msg)


def _wait_execution(
    build_id: str,
    stream_name_prefix: str,
    codebuild_log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    start_time: Optional[datetime] = None
    stream_name: Optional[str] = None
    for status in codebuild.wait(build_id=build_id):
        if codebuild_log_callback is not None and status.logs.enabled and status.logs.group_name:
            if stream_name is None:
                stream_name = cloudwatch.get_stream_name_by_prefix(
                    group_name=status.logs.group_name,
                    prefix=f"{stream_name_prefix}/",
                )
            if stream_name is not None:
                events = cloudwatch.get_log_events(
                    group_name=status.logs.group_name,
                    stream_name=stream_name,
                    start_time=start_time,
                )
                _print_codebuild_logs(events=events.events, codebuild_log_callback=codebuild_log_callback)
                if events.last_timestamp is not None:
                    start_time = events.last_timestamp + timedelta(milliseconds=1)


def _execute_codebuild(
    context: "Context",
    command_name: str,
    buildspec: codebuild.SPEC_TYPE,
    timeout: int,
    codebuild_log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    if context.toolkit.s3_bucket is None:
        raise ValueError(f"context.toolkit.s3_bucket: {context.toolkit.s3_bucket}")
    bundle_location = f"{context.toolkit.s3_bucket}/cli/remote/{command_name}/bundle.zip"
    _logger.debug("bundle_location: %s", bundle_location)
    stream_name_prefix = f"{command_name}-{int(datetime.now(timezone.utc).timestamp() * 1_000_000)}"
    _logger.debug("stream_name_prefix: %s", stream_name_prefix)
    build_id = codebuild.start(
        context=context,
        project_name=context.toolkit.codebuild_project,
        stream_name=stream_name_prefix,
        bundle_location=bundle_location,
        buildspec=buildspec,
        timeout=timeout,
    )
    _wait_execution(
        build_id=build_id,
        stream_name_prefix=stream_name_prefix,
        codebuild_log_callback=codebuild_log_callback,
    )


def run(
    command_name: str,
    context: "Context",
    bundle_path: str,
    buildspec: codebuild.SPEC_TYPE,
    timeout: int,
    codebuild_log_callback: Optional[Callable[[str], None]] = None,
) -> None:
    if context.toolkit.s3_bucket is None:
        raise ValueError(f"context.toolkit.s3_bucket: {context.toolkit.s3_bucket}")
    bucket: str = context.toolkit.s3_bucket
    key: str = f"cli/remote/{command_name}/bundle.zip"
    s3.delete_objects(bucket=bucket, keys=[key])
    s3.upload_file(src=bundle_path, bucket=bucket, key=key)
    _execute_codebuild(
        context=context,
        command_name=command_name,
        buildspec=buildspec,
        codebuild_log_callback=codebuild_log_callback,
        timeout=timeout,
    )
    s3.delete_objects(bucket=bucket, keys=[key])
