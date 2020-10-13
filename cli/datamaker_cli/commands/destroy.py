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

from datamaker_cli.manifest import Manifest, read_manifest_file
from datamaker_cli.messages import MessagesContext
from datamaker_cli.remote import execute_remote
from datamaker_cli.services import s3
from datamaker_cli.services.cfn import destroy_stack
from datamaker_cli.utils import does_cfn_exist

_logger: logging.Logger = logging.getLogger(__name__)


def _toolkit_pre_cleanup(env_name: str, account_id: str) -> None:
    s3.delete_bucket(f"datamaker-{env_name}-toolkit-{account_id}")


def destroy_toolkit(manifest: Manifest) -> None:
    stack_name = f"datamaker-{manifest.name}-toolkit"
    if does_cfn_exist(stack_name=stack_name):
        _toolkit_pre_cleanup(env_name=manifest.name, account_id=manifest.account_id)
        destroy_stack(stack_name=stack_name)


def destroy(filename: str, debug: bool) -> None:
    with MessagesContext("Destroying", debug=debug) as ctx:
        manifest = read_manifest_file(filename=filename)
        ctx.info(f"Manifest loaded: {filename}")
        ctx.info(f"Teams: {','.join([t.name for t in manifest.teams])}")
        ctx.progress(2)

        execute_remote(filename=filename, manifest=manifest, command="destroy", progress_callback=ctx.progress_callback)
        ctx.info("Toolkit destroyed")
        ctx.progress(85)

        destroy_toolkit(manifest=manifest)
        ctx.info("Toolkit destroyed")
        ctx.progress(100)
