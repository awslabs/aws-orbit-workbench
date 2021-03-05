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

from aws_orbit import cdk, sh
from aws_orbit.models.context import Context, ContextSerDe, TeamContext
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
    if len(sys.argv) != 5:
        raise ValueError(f"Unexpected number of values in sys.argv ({len(sys.argv)}) - {sys.argv}.")

    stack_name: str = sys.argv[1]
    team_name: str = sys.argv[3]
    parameters: Dict[str, Any] = _deserialize_parameters(parameters=sys.argv[4])
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=sys.argv[2], type=Context)
    team_context = context.get_team_by_name(name=team_name)
    if team_context is None:
        raise ValueError(f"Team {team_name} not found in the context.")

    outdir = os.path.join(
        ".orbit.out",
        context.name,
        "cdk",
        stack_name,
    )
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)

    # Can't be imported globally because we only have CDK installed on CodeBuild
    from aws_cdk.core import App

    app = App(outdir=outdir)
    stack_class(app, stack_name, context, team_context, parameters)  # type: ignore
    app.synth(force=True)


def cdk_prep_team_handler(stack_class: Type["Stack"]) -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) != 5:
        raise ValueError(f"Unexpected number of values in sys.argv ({len(sys.argv)}) - {sys.argv}.")

    stack_name: str = sys.argv[1]
    # team_name: str = sys.argv[3]
    parameters: Dict[str, Any] = _deserialize_parameters(parameters=sys.argv[4])
    context: "Context" = ContextSerDe.load_context_from_ssm(env_name=sys.argv[2], type=Context)

    # Can not find /orbit/env_name/teams ssm param.
    # team_context = context.get_team_by_name(name=team_name)
    # if team_context is None:
    #     raise ValueError(f"Team {team_name} not found in the context.")

    outdir = os.path.join(
        ".orbit.out",
        context.name,
        "cdk",
        stack_name,
    )
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)

    # Can't be imported globally because we only have CDK installed on CodeBuild
    from aws_cdk.core import App

    app = App(outdir=outdir)
    stack_class(app, stack_name, context, parameters)  # type: ignore
    app.synth(force=True)


def cdk_deploy(
    stack_name: str,
    app_filename: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    if context.cdk_toolkit.stack_name is None:
        raise ValueError(f"context.cdk_toolkit_stack_name: {context.cdk_toolkit.stack_name}")
    args: List[str] = [stack_name, context.name, team_context.name, _serialize_parameters(parameters=parameters)]
    cmd: str = (
        "cdk deploy --require-approval never --progress events "
        f"--toolkit-stack-name {context.cdk_toolkit.stack_name} "
        f"{cdk.get_app_argument(app_filename, args)} "
        f"{cdk.get_output_argument(context, stack_name)}"
    )
    sh.run(cmd=cmd)


def cdk_destroy(
    stack_name: str,
    app_filename: str,
    context: "Context",
    team_context: "TeamContext",
    parameters: Dict[str, Any],
) -> None:
    if cfn.does_stack_exist(stack_name=stack_name) is False:
        _logger.debug("Skipping CDK destroy for %s, because the stack was not found.", stack_name)
        return
    if context.cdk_toolkit.stack_name is None:
        raise ValueError(f"context.cdk_toolkit_stack_name: {context.cdk_toolkit.stack_name}")
    args: List[str] = [stack_name, context.name, team_context.name, _serialize_parameters(parameters=parameters)]
    cmd: str = (
        "cdk destroy --force "
        f"--toolkit-stack-name {context.cdk_toolkit.stack_name} "
        f"{cdk.get_app_argument(app_filename, args)} "
        f"{cdk.get_output_argument(context, stack_name)}"
    )
    sh.run(cmd=cmd)
