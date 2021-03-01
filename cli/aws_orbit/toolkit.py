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
import os
import shutil

import yaml
from cfn_flip import yaml_dumper
from cfn_tools import load_yaml

from aws_orbit import ORBIT_CLI_ROOT
from aws_orbit.models.context import Context

_logger: logging.Logger = logging.getLogger(__name__)

FILENAME = "template.yaml"
MODEL_FILENAME = os.path.join(ORBIT_CLI_ROOT, "data", "toolkit", FILENAME)


def synth(context: "Context", top_level: str = "orbit") -> str:
    outdir = os.path.join(os.getcwd(), ".orbit.out", context.name, "toolkit")
    try:
        shutil.rmtree(outdir)
    except FileNotFoundError:
        pass
    os.makedirs(outdir, exist_ok=True)
    output_filename = os.path.join(outdir, FILENAME)

    _logger.debug("Reading %s", MODEL_FILENAME)
    with open(MODEL_FILENAME, "r") as file:
        template = load_yaml(file)
    _logger.debug(
        "manifest.name: %s | manifest.account_id: %s | manifest.region: %s | manifest.deploy_id: %s",
        context.name,
        context.account_id,
        context.region,
        context.toolkit.deploy_id,
    )

    if context.policies:
        template["Resources"]["AdminRole"]["Properties"]["ManagedPolicyArns"].extend(
            [f"arn:aws:iam::{context.account_id}:policy/{policy}" for policy in context.policies]
        )

    content: str = yaml.dump(template, Dumper=yaml_dumper.get_dumper())
    content = content.replace("$", "").format(
        top_level=top_level,
        env_name=context.name,
        account_id=context.account_id,
        region=context.region,
        deploy_id=context.toolkit.deploy_id,
    )
    _logger.debug("Writing %s", output_filename)
    os.makedirs(outdir, exist_ok=True)
    with open(output_filename, "w") as file:
        file.write(content)

    return output_filename
