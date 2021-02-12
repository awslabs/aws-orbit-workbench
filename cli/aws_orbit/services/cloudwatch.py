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

from datetime import datetime, timezone
from typing import Dict, List, NamedTuple, Optional, Union, cast

from aws_orbit.utils import boto3_client


class CloudWatchEvent(NamedTuple):
    timestamp: datetime
    message: str


class CloudWatchEvents(NamedTuple):
    group_name: str
    stream_name_prefix: str
    start_time: Optional[datetime]
    events: List[CloudWatchEvent]
    last_timestamp: Optional[datetime]


def get_stream_name_by_prefix(group_name: str, prefix: str) -> Optional[str]:
    client = boto3_client("logs")
    response: Dict[str, Union[str, List[Dict[str, Union[float, str]]]]] = client.describe_log_streams(
        logGroupName=group_name,
        logStreamNamePrefix=prefix,
        orderBy="LogStreamName",
        descending=True,
        limit=1,
    )
    streams = cast(List[Dict[str, Union[float, str]]], response.get("logStreams", []))
    if streams:
        return str(streams[0]["logStreamName"])
    return None


def get_log_events(
    group_name: str,
    stream_name: str,
    start_time: Optional[datetime],
) -> CloudWatchEvents:
    client = boto3_client("logs")
    args = {
        "logGroupName": group_name,
        "logStreamName": stream_name,
        "startFromHead": True,
    }
    if start_time is not None:
        args["startTime"] = int(start_time.timestamp() * 1000)
    events: List[CloudWatchEvent] = []
    response: Dict[str, Union[str, List[Dict[str, Union[float, str]]]]] = client.get_log_events(**args)
    previous_token = None
    token = response["nextBackwardToken"]
    while response.get("events"):
        for event in cast(List[Dict[str, Union[float, str]]], response.get("events", [])):
            events.append(
                CloudWatchEvent(
                    timestamp=datetime.fromtimestamp(cast(int, event["timestamp"]) / 1000.0).astimezone(timezone.utc),
                    message=str(event.get("message", "")),
                )
            )
        previous_token = token
        token = response["nextBackwardToken"]
        if token == previous_token:
            break
        args["nextToken"] = token
        response = client.get_log_events(**args)
    events.sort(key=lambda e: e.timestamp, reverse=False)
    return CloudWatchEvents(
        group_name=group_name,
        stream_name_prefix=stream_name,
        start_time=start_time,
        events=events,
        last_timestamp=events[-1].timestamp if events else None,
    )
