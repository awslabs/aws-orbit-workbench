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

from aws_orbit import ORBIT_CLI_ROOT, sh, utils
from aws_orbit.models.context import Context
from aws_orbit.remote_files.utils import get_k8s_context

_logger: logging.Logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(ORBIT_CLI_ROOT, "data", "kubeflow")


def _cleanup_output(output_path: str) -> None:
    files = os.listdir(output_path)
    for file in files:
        if file.endswith(".yaml"):
            os.remove(os.path.join(output_path, file))


def gen_kubeflow_config(context: Context, output_path: str, cluster_name: str) -> None:

    os.makedirs(output_path, exist_ok=True)
    _cleanup_output(output_path=output_path)
    if context.account_id is None:
        raise RuntimeError("context.account_id is None!")
    if context.region is None:
        raise RuntimeError("context.region is None!")

    input = os.path.join(CONFIG_PATH, "kfctl_aws.yaml")
    output = os.path.join(output_path, "kfctl_aws.yaml")

    with open(input, "r") as file:
        content: str = file.read()

    content = utils.resolve_parameters(
        content,
        dict(
            certArn=context.networking.frontend.ssl_cert_arn,
            cognitoAppClientId=context.user_pool_client_id,
            cognitoUserPoolID=context.user_pool_id,
            account_id=context.account_id,
            region=context.region,
            env_name=context.name,
            cluster_name=cluster_name
        ),
    )
    _logger.debug("Kubeflow configuration:\n%s", content)
    with open(output, "w") as file:
        file.write(content)

    k8s_context = get_k8s_context(context=context)

    input = os.path.join(CONFIG_PATH, "kubeflow.sh")
    output = os.path.join(output_path, "kubeflow.sh")

    with open(input, "r") as file:
        content = file.read()

    content = utils.resolve_parameters(
        content,
        dict(cluster_name=cluster_name, k8s_context=k8s_context),
    )
    _logger.debug("Kubeflow script:\n%s", content)
    with open(output, "w") as file:
        file.write(content)

    sh.run(f"chmod a+x  {output}")


def deploy_kubeflow(context: Context) -> None:
    cluster_name = f"orbit-{context.name}"
    output_path = os.path.join(".orbit.out", context.name, "kubeflow", cluster_name)
    gen_kubeflow_config(context, output_path, cluster_name)

    _logger.debug("Deploying Kubeflow")
    output_path = os.path.abspath(output_path)
    _logger.debug(f"kubeflow config dir: {output_path}")
    utils.print_dir(output_path)
    sh.run("./kubeflow.sh", cwd=output_path)
