import logging
import os
from typing import List

from aws_orbit import sh
from aws_orbit.manifest import Manifest
from aws_orbit.services import cfn

_logger: logging.Logger = logging.getLogger(__name__)


def get_app_argument(app_filename: str, args: List[str]) -> str:
    args_str: str = " ".join(args)
    return f'--app "python {app_filename} {args_str}"'


def get_output_argument(manifest: Manifest, stack_name: str) -> str:
    path: str = os.path.join(".orbit.out", manifest.name, "cdk", stack_name)
    return f"--output {path}"


def deploy(manifest: Manifest, stack_name: str, app_filename: str, args: List[str]) -> None:
    if manifest.cdk_toolkit_stack_name is None:
        raise ValueError(f"manifest.cdk_toolkit_stack_name: {manifest.cdk_toolkit_stack_name}")
    cmd: str = (
        "cdk deploy --require-approval never --progress events "
        f"--toolkit-stack-name {manifest.cdk_toolkit_stack_name} "
        f"{get_app_argument(app_filename, args)} "
        f"{get_output_argument(manifest, stack_name)}"
    )
    sh.run(cmd=cmd)


def destroy(manifest: Manifest, stack_name: str, app_filename: str, args: List[str]) -> None:
    if cfn.does_stack_exist(manifest=manifest, stack_name=stack_name) is False:
        _logger.debug("Skipping CDK destroy for %s, because the stack was not found.", stack_name)
        return
    if manifest.cdk_toolkit_stack_name is None:
        raise ValueError(f"manifest.cdk_toolkit_stack_name: {manifest.cdk_toolkit_stack_name}")
    cmd: str = (
        "cdk destroy --force "
        f"--toolkit-stack-name {manifest.cdk_toolkit_stack_name} "
        f"{get_app_argument(app_filename, args)} "
        f"{get_output_argument(manifest, stack_name)}"
    )
    sh.run(cmd=cmd)


def deploy_toolkit(manifest: Manifest) -> None:
    if manifest.cdk_toolkit_stack_name is None:
        raise ValueError(f"manifest.cdk_toolkit_stack_name: {manifest.cdk_toolkit_stack_name}")
    cmd: str = (
        f"cdk bootstrap --toolkit-bucket-name {manifest.cdk_toolkit_s3_bucket} "
        f"--toolkit-stack-name {manifest.cdk_toolkit_stack_name} "
        f"{get_output_argument(manifest, manifest.cdk_toolkit_stack_name)} "
        f"aws://{manifest.account_id}/{manifest.region}"
    )
    sh.run(cmd=cmd)
