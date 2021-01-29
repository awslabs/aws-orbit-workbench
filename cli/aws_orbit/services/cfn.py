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
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, cast

import botocore.exceptions

from aws_orbit.services import s3

if TYPE_CHECKING:
    from aws_orbit.manifest import Manifest

CHANGESET_PREFIX = "aws-orbit-cli-deploy-"

_logger: logging.Logger = logging.getLogger(__name__)


def get_stack_status(manifest: "Manifest", stack_name: str) -> str:
    client = manifest.boto3_client("cloudformation")
    try:
        resp = client.describe_stacks(StackName=stack_name)
        if len(resp["Stacks"]) < 1:
            raise ValueError(f"CloudFormation stack {stack_name} not found.")
    except botocore.exceptions.ClientError:
        raise
    return cast(str, resp["Stacks"][0]["StackStatus"])


def get_eventual_consistency_event(manifest: "Manifest", stack_name: str) -> Optional[str]:
    if get_stack_status(manifest=manifest, stack_name=stack_name) not in ("ROLLBACK_COMPLETE", "ROLLBACK_FAILED"):
        return None
    client = manifest.boto3_client("cloudformation")
    paginator = client.get_paginator("describe_stack_events")
    response_iterator = paginator.paginate(StackName=stack_name)
    _logger.debug("Scanning %s events for eventual consistency issue", stack_name)
    for resp in response_iterator:
        for event in resp["StackEvents"]:
            if event["ResourceStatus"] == "CREATE_FAILED":
                logical_id = cast(str, event["LogicalResourceId"])
                _logger.debug("Resource %s has status CREATE_FAILED", logical_id)
                if "there is already a conflicting DNS domain" in event["ResourceStatusReason"]:
                    _logger.warn("Resource %s had a eventual consistency issue!", logical_id)
                    return logical_id
    return None


def does_stack_exist(manifest: "Manifest", stack_name: str) -> bool:
    client = manifest.boto3_client("cloudformation")
    try:
        resp = client.describe_stacks(StackName=stack_name)
        if len(resp["Stacks"]) < 1:
            return False
    except botocore.exceptions.ClientError as ex:
        error: Dict[str, Any] = ex.response["Error"]
        if error["Code"] == "ValidationError" and f"Stack with id {stack_name} does not exist" in error["Message"]:
            return False
        raise
    return True


def _wait_for_changeset(manifest: "Manifest", changeset_id: str, stack_name: str) -> bool:
    waiter = manifest.boto3_client("cloudformation").get_waiter("change_set_create_complete")
    waiter_config = {"Delay": 1}
    try:
        waiter.wait(ChangeSetName=changeset_id, StackName=stack_name, WaiterConfig=waiter_config)
    except botocore.exceptions.WaiterError as ex:
        resp = ex.last_response
        status = resp["Status"]
        reason = resp["StatusReason"]
        if (
            status == "FAILED"
            and "The submitted information didn't contain changes." in reason
            or "No updates are to be performed" in reason
        ):
            _logger.debug(f"No changes for {stack_name} CloudFormation stack.")
            return False
        raise RuntimeError(f"Failed to create the changeset: {ex}. Status: {status}. Reason: {reason}")
    return True


def _create_changeset(
    manifest: "Manifest", stack_name: str, template_str: str, env_tag: str, template_path: str = ""
) -> Tuple[str, str]:
    now = datetime.utcnow().isoformat()
    description = f"Created by AWS Orbit Workbench CLI at {now} UTC"
    changeset_name = CHANGESET_PREFIX + str(int(time.time()))
    changeset_type = "UPDATE" if does_stack_exist(manifest=manifest, stack_name=stack_name) else "CREATE"
    kwargs = {
        "ChangeSetName": changeset_name,
        "StackName": stack_name,
        "ChangeSetType": changeset_type,
        "Capabilities": ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
        "Description": description,
        "Tags": ({"Key": "Env", "Value": env_tag},),
    }
    if template_str:
        kwargs.update({"TemplateBody": template_str})
    elif template_path:
        _logger.info(f"template_path={template_path}")
        kwargs.update({"TemplateURL": template_path})
    resp = manifest.boto3_client("cloudformation").create_change_set(**kwargs)
    return str(resp["Id"]), changeset_type


def _execute_changeset(manifest: "Manifest", changeset_id: str, stack_name: str) -> None:
    manifest.boto3_client("cloudformation").execute_change_set(ChangeSetName=changeset_id, StackName=stack_name)


def _wait_for_execute(manifest: "Manifest", stack_name: str, changeset_type: str) -> None:
    if changeset_type == "CREATE":
        waiter = manifest.boto3_client("cloudformation").get_waiter("stack_create_complete")
    elif changeset_type == "UPDATE":
        waiter = manifest.boto3_client("cloudformation").get_waiter("stack_update_complete")
    else:
        raise RuntimeError(f"Invalid changeset type {changeset_type}")
    waiter_config = {
        "Delay": 5,
        "MaxAttempts": 480,
    }
    waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)


def deploy_template(manifest: "Manifest", stack_name: str, filename: str, env_tag: str) -> None:
    _logger.debug("Deploying template %s", filename)
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"CloudFormation template not found at {filename}")
    template_size = os.path.getsize(filename)
    if template_size > 51_200:
        if manifest.toolkit_s3_bucket is None:
            manifest.fetch_toolkit_data()
            if manifest.toolkit_s3_bucket is None:
                raise ValueError("manifest.toolkit_s3_bucket: %s", manifest.toolkit_s3_bucket)
        _logger.info(f"The CloudFormation template ({filename}) is too big to be deployed, using s3 bucket.")
        local_template_path = filename
        s3_file_name = filename.split("/")[-1]
        key = f"cli/remote/demo/{s3_file_name}"
        s3_template_path = f"https://s3.amazonaws.com/{manifest.toolkit_s3_bucket}/{key}"
        _logger.debug("s3_template_path: %s", s3_template_path)
        s3.upload_file(manifest=manifest, src=local_template_path, bucket=manifest.toolkit_s3_bucket, key=key)
        time.sleep(3)  # Avoiding eventual consistence issues
        changeset_id, changeset_type = _create_changeset(
            manifest=manifest, stack_name=stack_name, template_str="", env_tag=env_tag, template_path=s3_template_path
        )
    else:
        with open(filename, "r") as handle:
            template_str = handle.read()
        changeset_id, changeset_type = _create_changeset(
            manifest=manifest, stack_name=stack_name, template_str=template_str, env_tag=env_tag
        )
    has_changes = _wait_for_changeset(manifest, changeset_id, stack_name)
    if has_changes:
        _execute_changeset(manifest=manifest, changeset_id=changeset_id, stack_name=stack_name)
        _wait_for_execute(manifest=manifest, stack_name=stack_name, changeset_type=changeset_type)


def destroy_stack(manifest: "Manifest", stack_name: str) -> None:
    _logger.debug("Destroying stack %s", stack_name)
    client = manifest.boto3_client("cloudformation")
    client.delete_stack(StackName=stack_name)
    waiter = client.get_waiter("stack_delete_complete")
    waiter.wait(StackName=stack_name, WaiterConfig={"Delay": 5, "MaxAttempts": 200})
