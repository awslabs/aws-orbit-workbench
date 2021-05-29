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
from typing import Any, Dict, Optional

import aws_orbit_sdk.controller as controller

_logger: logging.Logger = logging.getLogger(__name__)


def _set_environ(env: str, team: str, user: str) -> None:
    os.environ["AWS_ORBIT_ENV"] = env
    os.environ["AWS_ORBIT_TEAM_SPACE"] = team
    os.environ["USERNAME"] = user
    os.environ["AWS_ORBIT_S3_BUCKET"] = "Unknown"


def _wait(tasks: Dict[str, Any], delay: Optional[int], max_attempts: Optional[int], tail_logs: bool) -> bool:
    params = {"tasks": [tasks], "tail_log": tail_logs}
    if delay:
        params["delay"] = delay
    if max_attempts:
        params["maxAttempts"] = max_attempts
    no_error: bool = controller.wait_for_tasks_to_complete(**params)
    return no_error


def run_python_container(
    env: str,
    team: str,
    user: str,
    tasks: Dict[str, Any],
    wait: bool,
    delay: Optional[int],
    max_attempts: Optional[int],
    tail_logs: bool,
    debug: bool,
) -> bool:
    if debug:
        controller._logger.setLevel(logging.DEBUG)
    _set_environ(env, team, user)
    response = controller.run_python(tasks)
    if wait:
        return _wait(response, delay, max_attempts, tail_logs)
    else:
        print(json.dumps(response))
        return True


def run_notebook_container(
    env: str,
    team: str,
    user: str,
    tasks: Dict[str, Any],
    wait: bool,
    delay: Optional[int],
    max_attempts: Optional[int],
    tail_logs: bool,
    debug: bool,
) -> bool:
    if debug:
        controller._logger.setLevel(logging.DEBUG)
    _set_environ(env, team, user)
    response = controller.run_notebooks(tasks)
    if wait:
        return _wait(response, delay, max_attempts, tail_logs)
    else:
        print(json.dumps(response))
        return True
