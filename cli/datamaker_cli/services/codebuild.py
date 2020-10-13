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
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Union

import boto3
import yaml

_logger: logging.Logger = logging.getLogger(__name__)


_BUILD_WAIT_POLLING_DELAY: float = 2  # SECONDS

CDK_VERSION = "~=1.67.0"
CDK_MODULES = [
    "aws_cdk.core",
    "aws-cdk.aws-ec2",
    "aws-cdk.aws-iam",
    "aws-cdk.aws-efs",
    "aws-cdk.aws-ecr",
    "aws-cdk.aws-ecs",
    "aws-cdk.aws-ssm",
    "aws_cdk.aws_cognito",
]


class BuildStatus(Enum):
    failed = "FAILED"
    fault = "FAULT"
    in_progress = "IN_PROGRESS"
    stopped = "STOPPED"
    succeeded = "SUCCEEDED"
    timed_out = "TIMED_OUT"


class BuildPhaseType(Enum):
    build = "BUILD"
    completed = "COMPLETED"
    download_source = "DOWNLOAD_SOURCE"
    finalizing = "FINALIZING"
    install = "INSTALL"
    post_build = "POST_BUILD"
    pre_build = "PRE_BUILD"
    provisioning = "PROVISIONING"
    queued = "QUEUED"
    submitted = "SUBMITTED"
    upload_artifacts = "UPLOAD_ARTIFACTS"


class BuildPhaseStatus(Enum):
    failed = "FAILED"
    fault = "FAULT"
    queued = "QUEUED"
    in_progress = "IN_PROGRESS"
    stopped = "STOPPED"
    succeeded = "SUCCEEDED"
    timed_out = "TIMED_OUT"


class BuildPhaseContext(NamedTuple):
    status_code: Optional[str]
    message: Optional[str]


class BuildPhase(NamedTuple):
    phase_type: BuildPhaseType
    status: Optional[BuildPhaseStatus]
    start_time: datetime
    end_time: Optional[datetime]
    duration_in_seconds: float
    contexts: List[BuildPhaseContext]


class BuildCloudWatchLogs(NamedTuple):
    enabled: bool
    group_name: Optional[str]
    stream_name: Optional[str]


class BuildInfo(NamedTuple):
    build_id: str
    status: BuildStatus
    current_phase: BuildPhaseType
    start_time: datetime
    end_time: Optional[datetime]
    duration_in_seconds: float
    phases: List[BuildPhase]
    logs: BuildCloudWatchLogs


def start(project_name: str, stream_name: str, bundle_location: str, spec: Dict[str, Any], timeout: int) -> str:
    client = boto3.client("codebuild")
    response: Dict[str, Any] = client.start_build(
        projectName=project_name,
        sourceTypeOverride="S3",
        sourceLocationOverride=bundle_location,
        buildspecOverride=yaml.safe_dump(data=spec, sort_keys=False, indent=4),
        timeoutInMinutesOverride=timeout,
        logsConfigOverride={
            "cloudWatchLogs": {
                "status": "ENABLED",
                "groupName": f"/aws/codebuild/{project_name}",
                "streamName": stream_name,
            },
            "s3Logs": {"status": "DISABLED"},
        },
    )
    return str(response["build"]["id"])


def fetch_build_info(build_id: str) -> BuildInfo:
    client = boto3.client("codebuild")
    response: Dict[str, List[Dict[str, Any]]] = client.batch_get_builds(ids=[build_id])
    if not response["builds"]:
        raise RuntimeError(f"CodeBuild build {build_id} not found.")
    build = response["builds"][0]
    now = datetime.now(timezone.utc)
    log_enabled = True if build.get("logs", {}).get("cloudWatchLogs", {}).get("status") == "ENABLED" else False
    return BuildInfo(
        build_id=build_id,
        status=BuildStatus(value=build["buildStatus"]),
        current_phase=BuildPhaseType(value=build["currentPhase"]),
        start_time=build["startTime"],
        end_time=build.get("endTime", now),
        duration_in_seconds=(build.get("endTime", now) - build["startTime"]).total_seconds(),
        phases=[
            BuildPhase(
                phase_type=BuildPhaseType(value=p["phaseType"]),
                status=None if "phaseStatus" not in p else BuildPhaseStatus(value=p["phaseStatus"]),
                start_time=p["startTime"],
                end_time=p.get("endTime", now),
                duration_in_seconds=p.get("durationInSeconds"),
                contexts=[
                    BuildPhaseContext(status_code=p.get("statusCode"), message=p.get("message"))
                    for c in p.get("contexts", [])
                ],
            )
            for p in build["phases"]
        ],
        logs=BuildCloudWatchLogs(
            enabled=log_enabled,
            group_name=build["logs"]["cloudWatchLogs"].get("groupName") if log_enabled else None,
            stream_name=build["logs"]["cloudWatchLogs"].get("streamName") if log_enabled else None,
        ),
    )


def wait(build_id: str) -> Iterable[BuildInfo]:
    build = fetch_build_info(build_id=build_id)
    while build.status is BuildStatus.in_progress:
        time.sleep(_BUILD_WAIT_POLLING_DELAY)
        build = fetch_build_info(build_id=build_id)
        _logger.debug("phase: %s (%s)", build.current_phase.value, build.status.value)
        yield build

    if build.status is not BuildStatus.succeeded:
        raise RuntimeError(f"CodeBuild build ({build_id}) is {build.status.value}")
    _logger.debug("start: %s | end: %s | elapsed: %s", build.start_time, build.end_time, build.duration_in_seconds)


SPEC_TYPE = Dict[str, Union[float, Dict[str, Dict[str, Union[List[str], Dict[str, float]]]]]]


def generate_spec(pre_cmds: List[str], build_cmds: List[str], post_cmds: List[str], bundle_location: str) -> SPEC_TYPE:
    pre_cmds_default = [
        f"aws s3 rm s3://{bundle_location}",
        "ls -la",
        "cd bundle",
        "ls -la",
        f"pip install kubernetes~=11.0.0 sh~=1.14.0 {' '.join([f'{m}{CDK_VERSION}' for m in CDK_MODULES])}",
        "pip install cli/",
    ]
    build_cmds_default = ["echo 'build'"]
    post_cmds_default = ["echo 'post_build'"]
    return {
        "version": 0.2,
        "phases": {
            "install": {"runtime-versions": {"python": 3.7, "nodejs": 12}},
            "pre_build": {"commands": pre_cmds_default + pre_cmds},
            "build": {"commands": build_cmds_default + build_cmds},
            "post_build": {"commands": post_cmds_default + post_cmds},
        },
    }
