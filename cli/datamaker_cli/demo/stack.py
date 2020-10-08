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

from aws_cdk.core import App

from datamaker_cli.demo.vpc import VpcStack
from datamaker_cli.utils import path_from_filename


def synth(stack_name: str, filename: str, env_name: str) -> str:
    outdir = f"{path_from_filename(filename=filename)}.datamaker.out/{env_name}/cdk/{stack_name}/"
    app = App(outdir=outdir)
    VpcStack(scope=app, id=stack_name, env_name=env_name)
    app.synth(force=True)
    cfn_template_filename = f"{outdir}{stack_name}.template.json"
    return cfn_template_filename
