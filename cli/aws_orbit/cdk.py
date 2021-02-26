import logging
import os
from typing import TYPE_CHECKING, Generic, List, TypeVar

from aws_orbit import sh
from aws_orbit.models.context import Context, FoundationContext
from aws_orbit.services import cfn

_logger: logging.Logger = logging.getLogger(__name__)

T = TypeVar("T")


def get_app_argument(app_filename: str, args: List[str]) -> str:
    args_str: str = " ".join(args)
    return f'--app "python {app_filename} {args_str}"'


def get_output_argument(context: T, stack_name: str) -> str:
    if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
        raise ValueError("Unknown 'context' Type")
    path: str = os.path.join(".orbit.out", context.name, "cdk", stack_name)
    return f"--output {path}"


def deploy(context: T, stack_name: str, app_filename: str, args: List[str]) -> None:
    if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
        raise ValueError("Unknown 'context' Type")
    cmd: str = (
        "cdk deploy --require-approval never --progress events "
        f"--toolkit-stack-name {context.cdk_toolkit.stack_name} "
        f"{get_app_argument(app_filename, args)} "
        f"{get_output_argument(context, stack_name)}"
    )
    sh.run(cmd=cmd)


def destroy(context: T, stack_name: str, app_filename: str, args: List[str]) -> None:
    if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
        raise ValueError("Unknown 'context' Type")
    if cfn.does_stack_exist(stack_name=stack_name) is False:
        _logger.debug("Skipping CDK destroy for %s, because the stack was not found.", stack_name)
        return
    cmd: str = (
        "cdk destroy --force "
        f"--toolkit-stack-name {context.cdk_toolkit.stack_name} "
        f"{get_app_argument(app_filename, args)} "
        f"{get_output_argument(context, stack_name)}"
    )
    sh.run(cmd=cmd)


def deploy_toolkit(context: T) -> None:
    if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
        raise ValueError("Unknown 'context' Type")
    cmd: str = (
        f"cdk bootstrap --toolkit-bucket-name {context.cdk_toolkit.s3_bucket} "
        f"--toolkit-stack-name {context.cdk_toolkit.stack_name} "
        f"{get_output_argument(context, context.cdk_toolkit.stack_name)} "
        f"aws://{context.account_id}/{context.region}"
    )
    sh.run(cmd=cmd)
