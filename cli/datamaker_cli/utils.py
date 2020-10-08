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

from typing import TYPE_CHECKING, Any, Dict, Iterable, List

import boto3
import botocore.exceptions
import click
from kubernetes import config

if TYPE_CHECKING:
    from datamaker_cli.manifest import Manifest


def stylize(text: str) -> str:
    return click.style(text=text, bold=True, fg="bright_blue")


def get_region() -> str:
    session = boto3.Session()
    if session.region_name is None:
        raise ValueError(
            "It is not possible to infer AWS REGION from your environment. Please pass the --region argument."
        )
    return str(session.region_name)


def get_account_id() -> str:
    return str(boto3.client(service_name="sts").get_caller_identity().get("Account"))


def namedtuple_to_dict(obj: Any) -> Any:
    if hasattr(obj, "_asdict"):  # NamedTuple
        return dict(zip(obj._fields, (namedtuple_to_dict(item) for item in obj)))
    elif isinstance(obj, str):
        return obj
    elif isinstance(obj, dict):
        return dict(zip(obj.keys(), (namedtuple_to_dict(item) for item in obj.values())))
    elif isinstance(obj, Iterable):
        return list((namedtuple_to_dict(item) for item in obj))
    return obj


def does_cfn_exist(stack_name: str) -> bool:
    client = boto3.client("cloudformation")
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


def path_from_filename(filename: str) -> str:
    if "/" in filename:
        return filename.rsplit(sep="/", maxsplit=1)[0] + "/"
    return "./"


def upsert_subnet_tag(subnet_id: str, key: str, value: str) -> None:
    ec2: Any = boto3.resource("ec2")
    ec2.Subnet(subnet_id).create_tags(Tags=[{"Key": key, "Value": value}])


def replace_dashes(original: Dict[str, Any]) -> Dict[str, Any]:
    return {k.replace("-", "_"): v for k, v in original.items()}


def replace_underscores(original: Dict[str, Any]) -> Dict[str, Any]:
    return {k.replace("_", "-"): v for k, v in original.items()}


def get_k8s_context(manifest: "Manifest") -> str:
    try:
        contexts: List[str] = [str(c["name"]) for c in config.list_kube_config_contexts()[0]]
    except config.config_exception.ConfigException:
        raise RuntimeError("Context not found")
    expected_domain: str = f"@datamaker-{manifest.name}.{manifest.region}.eksctl.io"
    for context in contexts:
        if context.endswith(expected_domain):
            return context
    raise RuntimeError(f"Context not found for domain: {expected_domain}")
