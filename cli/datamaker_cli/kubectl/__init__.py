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

import sh

from datamaker_cli import DATAMAKER_CLI_ROOT
from datamaker_cli.manifest import Manifest, TeamManifest
from datamaker_cli.spinner import start_spinner
from datamaker_cli.utils import does_cfn_exist, path_from_filename

_logger: logging.Logger = logging.getLogger(__name__)


EFS_DRIVE = "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/ecr/?ref=release-1.0"
MODEL_PATH: str = f"{DATAMAKER_CLI_ROOT}/kubectl/models/"


def _commons(output_path: str) -> None:
    filename = "00-commons.yaml"
    input = MODEL_PATH + filename
    output = output_path + filename
    shutil.copyfile(src=input, dst=output)


def _team(region: str, account_id: str, output_path: str, env_name: str, team: TeamManifest) -> None:
    input = MODEL_PATH + "01-team.yaml"
    output = output_path + f"01-{team.name}-team.yaml"

    with open(input, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        team=team.name, efsid=team.efs_id, region=region, account_id=account_id, env_name=env_name
    )
    with open(output, "w") as file:
        file.write(content)

    # user service account
    input = MODEL_PATH + "02-user-service-account.yaml"
    output = output_path + f"02-{team.name}-user-service-account.yaml"

    with open(input, "r") as file:
        content = file.read()
    content = content.replace("$", "").format(team=team.name, efsid=team.efs_id, region=region, account_id=account_id)
    with open(output, "w") as file:
        file.write(content)


def _landing_page(
    region: str,
    account_id: str,
    output_path: str,
    env_name: str,
    user_pool_id: str,
    user_pool_client_id: str,
    identity_pool_id: str,
) -> None:
    filename = "03-landing-page.yaml"
    input = MODEL_PATH + filename
    output = output_path + filename
    with open(input, "r") as file:
        content: str = file.read()
    content = content.replace("$", "").format(
        region=region,
        account_id=account_id,
        env_name=env_name,
        user_pool_id=user_pool_id,
        user_pool_client_id=user_pool_client_id,
        identity_pool_id=identity_pool_id,
    )
    with open(output, "w") as file:
        file.write(content)


def _cleanup_output(output_path: str) -> None:
    files = os.listdir(output_path)
    for file in files:
        if file.endswith(".yaml"):
            os.remove(os.path.join(output_path, file))


def _generate_manifest(manifest: Manifest, filename: str) -> str:

    output_path = f"{path_from_filename(filename=filename)}.datamaker.out/{manifest.name}/kubectl/"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    _cleanup_output(output_path=output_path)
    _commons(output_path=output_path)

    if manifest.account_id is None:
        raise RuntimeError("manifest.account_id is None!")

    for team in manifest.teams:
        _team(
            region=manifest.region,
            account_id=manifest.account_id,
            env_name=manifest.name,
            output_path=output_path,
            team=team,
        )

    if manifest.user_pool_id is None:
        _logger.warning("manifest.user_pool_id is None, skipping LandingPage Manifest generation.")
        return output_path
    if manifest.user_pool_client_id is None:
        _logger.warning("manifest.user_pool_client_id is None, skipping LandingPage Manifest generation.")
        return output_path
    if manifest.identity_pool_id is None:
        _logger.warning("manifest.identity_pool_id is None, skipping LandingPage Manifest generation.")
        return output_path

    _landing_page(
        region=manifest.region,
        account_id=manifest.account_id,
        output_path=output_path,
        env_name=manifest.name,
        user_pool_id=manifest.user_pool_id,
        user_pool_client_id=manifest.user_pool_client_id,
        identity_pool_id=manifest.identity_pool_id,
    )

    return output_path


def deploy(manifest: Manifest, filename: str, context: str) -> Manifest:
    eks_stack_name: str = f"eksctl-datamaker-{manifest.name}-cluster"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)

    if does_cfn_exist(stack_name=eks_stack_name):

        with start_spinner(msg="Synthetizing KUBECTL manifests") as spinner:
            output_path = _generate_manifest(manifest=manifest, filename=filename)
            spinner.succeed()

        with start_spinner(msg="Deploying EFS driver") as spinner:
            sh.kubectl("apply", "-k", EFS_DRIVE, "--context", context)
            spinner.succeed()

        with start_spinner(msg="Deploying KUBECTL resources") as spinner:
            sh.kubectl("apply", "-f", output_path, "--context", context)
            spinner.succeed()

    return manifest


def destroy(manifest: Manifest, filename: str, context: str) -> Manifest:
    eks_stack_name: str = f"datamaker-{manifest.name}"
    _logger.debug("EKSCTL stack name: %s", eks_stack_name)

    if does_cfn_exist(stack_name=eks_stack_name) is True:

        with start_spinner(msg="Synthetizing KUBECTL manifests") as spinner:
            output_path = _generate_manifest(manifest=manifest, filename=filename)
            spinner.succeed()

        with start_spinner(msg="Destroying KUBECTL resources") as spinner:
            output_path = f"{path_from_filename(filename=filename)}.datamaker.out/{manifest.name}/kubectl/"
            _logger.debug("output_path: %s", output_path)
            try:
                sh.kubectl(
                    "delete",
                    "-f",
                    output_path,
                    "--grace-period=0",
                    "--force",
                    "--ignore-not-found",
                    "--context",
                    context,
                )
            except sh.ErrorReturnCode as ex:
                _logger.debug("Skipping:: %s", ex)
                pass  # Let's leave for eksctl, it will destroy everything anyway...
            spinner.succeed()

    return manifest
