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
from typing import Any, Dict, Optional, Sequence

import click
import tqdm

COLOR_DATAMAKER = "bright_blue"
COLOR_ERROR = "bright_red"
COLOR_WARN = "bright_yellow"

PROGRESS_BAR_FORMAT = "{desc} |{bar}| {percentage:3.0f}% "

_logger: logging.Logger = logging.getLogger(__name__)


def stylize(text: str, color: str = COLOR_DATAMAKER, bold: bool = False, underline: bool = False) -> str:
    return click.style(text=text, bold=bold, underline=underline, fg=color)


def print_list(tittle: str, items: Sequence[str]) -> None:
    click.echo(message=(f"{tittle}\n\n" + "\n".join([f"{stylize('>')} {i}" for i in items])))


REMOTE_PROGRESS_LOOKUP: Dict[str, Dict[str, int]] = {
    "Deploying": {
        "Waiting for agent ping": 20,
        "Waiting for DOWNLOAD_SOURCE": 21,
        "Phase is DOWNLOAD_SOURCE": 22,
        "Phase complete: DOWNLOAD_SOURCE State: SUCCEEDED": 23,
        "Running command npm install -g aws-cdk": 25,
        "Phase complete: INSTALL State: SUCCEEDED": 27,
        "Phase complete: PRE_BUILD State: SUCCEEDED": 30,
        "CDK Toolkit Stack deployed": 40,
        "Demo Stack deployed": 50,
        "Env Stack deployed": 55,
        "Docker images build skipped": 65,
        "Docker Images deployed": 65,
        "Teams Stacks deployed": 70,
        "EKS Stack deployed": 80,
        "Kubernetes components deployed": 95,
        "Phase complete: BUILD State: SUCCEEDED": 97,
    },
    "Destroying": {
        "Waiting for agent ping": 20,
        "Waiting for DOWNLOAD_SOURCE": 21,
        "Phase is DOWNLOAD_SOURCE": 22,
        "Phase complete: DOWNLOAD_SOURCE State: SUCCEEDED": 23,
        "Running command npm install -g aws-cdk": 25,
        "Phase complete: INSTALL State: SUCCEEDED": 27,
        "Phase complete: PRE_BUILD State: SUCCEEDED": 30,
        "Kubernetes components destroyed": 35,
        "EKS Stack destroyed": 40,
        "Teams Stacks destroyed": 65,
        "Env Stack destroyed": 75,
        "Demo Stack destroyed": 85,
        "CDK Toolkit Stack destroyed": 90,
        "Skipping Env, Demo, and CDK Toolkit Stacks": 90,
        "Phase complete: BUILD State: SUCCEEDED": 94,
    },
    "Deploying Docker Image": {
        "Waiting for agent ping": 20,
        "Waiting for DOWNLOAD_SOURCE": 21,
        "Phase is DOWNLOAD_SOURCE": 22,
        "Phase complete: DOWNLOAD_SOURCE State: SUCCEEDED": 23,
        "Running command npm install -g aws-cdk": 25,
        "Phase complete: INSTALL State: SUCCEEDED": 27,
        "Phase complete: PRE_BUILD State: SUCCEEDED": 30,
        "Env changes deployed": 70,
        "Logged in": 75,
        "Docker Image built": 85,
        "Docker Image Deployed to ECR": 97,
        "Phase complete: BUILD State: SUCCEEDED": 99,
    },
    "Destroying Docker Image": {
        "Waiting for agent ping": 20,
        "Waiting for DOWNLOAD_SOURCE": 21,
        "Phase is DOWNLOAD_SOURCE": 22,
        "Phase complete: DOWNLOAD_SOURCE State: SUCCEEDED": 23,
        "Running command npm install -g aws-cdk": 25,
        "Phase complete: INSTALL State: SUCCEEDED": 27,
        "Phase complete: PRE_BUILD State: SUCCEEDED": 30,
        "Env changes deployed": 70,
        "Docker Image Destroyed from ECR": 95,
        "Phase complete: BUILD State: SUCCEEDED": 99,
    },
}


class MessagesContext:
    def __init__(self, task_name: str, debug: bool) -> None:
        self.task_name = task_name
        self.debug = debug
        if self.debug:
            self.pbar = None
        else:
            self.pbar = tqdm.tqdm(
                total=100,
                desc=task_name,
                bar_format=PROGRESS_BAR_FORMAT,
                ncols=50,
                colour="green",
            )

    def __enter__(self) -> "MessagesContext":
        if self.pbar is not None:
            self.pbar.update(1)
        else:
            _logger.debug("Progress bar: 1%")
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, exc_traceback: Any) -> None:
        if exc_type is not None:
            self.error(f"{exc_type.__name__}: {exc_value}")
        if self.pbar is not None:
            self.pbar.write("")
            self.pbar.close()
        if exc_traceback is not None:
            click.echo(f"\n{stylize('Error Traceback', color=COLOR_ERROR)}:")

    def info(self, msg: str) -> None:
        tittle: str = stylize(text=" Info ", color="reset", bold=False, underline=False)
        self.echo(tittle=tittle, msg=msg)

    def tip(self, msg: str) -> None:
        tittle: str = stylize(text=" Tip ", color=COLOR_DATAMAKER, bold=False, underline=False)
        self.echo(tittle=tittle, msg=msg)

    def warn(self, msg: str) -> None:
        tittle: str = stylize(text=" Warn ", color=COLOR_WARN, bold=False, underline=False)
        self.echo(tittle=tittle, msg=msg)

    def error(self, msg: str) -> None:
        tittle: str = stylize(text=" Error ", color=COLOR_ERROR, bold=False, underline=False)
        self.echo(tittle=tittle, msg=msg)

    def echo(self, tittle: str, msg: str) -> None:
        text = f"[{tittle}] {msg}"
        if self.pbar is not None:
            self.pbar.write(text)
        else:
            click.echo(text)

    def progress(self, n: int) -> None:
        if self.pbar is not None:
            current = self.pbar.n
            if current > n:
                raise RuntimeError(f"Current progress: {current} | Desired progress: {n}")
            self.pbar.update(n - current)
        else:
            _logger.debug(f"Progress bar: {n}%")

    def _progress_codebuild_log(self, msg: str) -> bool:
        msg = msg[32:]
        n: Optional[int] = REMOTE_PROGRESS_LOOKUP[self.task_name].get(msg)
        if n is not None:
            self.progress(n=n)
            return True
        return False

    def _progress_cli_log(self, msg: str) -> bool:
        msg_begining = "] "
        if msg_begining in msg:
            n: Optional[int] = REMOTE_PROGRESS_LOOKUP[self.task_name].get(msg.split(sep=msg_begining, maxsplit=1)[-1])
            if n is not None:
                self.progress(n=n)
                return True
        return False

    def progress_bar_callback(self, msg: str) -> None:
        if self._progress_codebuild_log(msg=msg) is False:
            self._progress_cli_log(msg=msg)
