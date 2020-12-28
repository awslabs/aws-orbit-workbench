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

import ipaddress
import logging
import math
import os
import random
import time
from string import Template
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Union

import boto3
import botocore.exceptions

if TYPE_CHECKING:
    from aws_orbit.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def chunkify(lst: List[Any], num_chunks: int = 1, max_length: Optional[int] = None) -> List[List[Any]]:
    num: int = num_chunks if max_length is None else int(math.ceil((float(len(lst)) / float(max_length))))
    return [lst[i : i + num] for i in range(0, len(lst), num)]  # noqa: E203


def get_region() -> str:
    session = boto3.Session()
    if session.region_name is None:
        raise ValueError(
            "It is not possible to infer AWS REGION from your environment. Please pass the --region argument."
        )
    return str(session.region_name)


def get_account_id(manifest: "Manifest") -> str:
    return str(manifest.boto3_client(service_name="sts").get_caller_identity().get("Account"))


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


def path_from_filename(filename: str) -> str:
    return os.path.dirname(os.path.realpath(filename))


def upsert_subnet_tag(manifest: "Manifest", subnet_id: str, key: str, value: str) -> None:
    ec2: Any = manifest.boto3_resource("ec2")
    ec2.Subnet(subnet_id).create_tags(Tags=[{"Key": key, "Value": value}])


def replace_underscores(original: Dict[str, Any]) -> Dict[str, Any]:
    aux = {k.replace("_", "-"): v for k, v in original.items()}
    ret = {}
    for k, v in aux.items():
        if k.startswith("-"):
            ret[k[1:]] = v
        else:
            ret[k] = v
    return ret


def extract_plugin_module_name(func: Callable[..., Union[None, List[str], str]]) -> str:
    name = func.__module__.split(sep=".", maxsplit=1)[0]
    return name


def extract_images_names(manifest: "Manifest") -> List[str]:
    resp_type = Dict[str, List[Dict[str, List[Dict[str, str]]]]]
    try:
        response: resp_type = manifest.boto3_client("cloudformation").describe_stacks(
            StackName=f"orbit-{manifest.name}"
        )
    except botocore.exceptions.ClientError as ex:
        error: Dict[str, Any] = ex.response["Error"]
        if (
            error["Code"] == "ValidationError"
            and f"Stack with id orbit-{manifest.name} does not exist" in error["Message"]
        ):
            return []
        raise
    if len(response["Stacks"]) < 1:
        return []
    if "Outputs" not in response["Stacks"][0]:
        return []
    for output in response["Stacks"][0]["Outputs"]:
        if output["ExportName"] == f"orbit-{manifest.name}-repos":
            _logger.debug("Export value: %s", output["OutputValue"])
            return output["OutputValue"].split(",")
    raise RuntimeError(f"Stack orbit-{manifest.name} does not have the expected orbit-{manifest.name}-repos output.")


def try_it(
    f: Callable[..., Any],
    ex: Any,
    base: float = 1.0,
    max_num_tries: int = 3,
    **kwargs: Any,
) -> Any:
    """Run function with decorrelated Jitter.

    Reference: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
    """
    delay: float = base
    for i in range(max_num_tries):
        try:
            return f(**kwargs)
        except ex as exception:
            if i == (max_num_tries - 1):
                raise exception
            delay = random.uniform(base, delay * 3)
            _logger.error(
                "Retrying %s | Fail number %s/%s | Exception: %s",
                f,
                i + 1,
                max_num_tries,
                exception,
            )
            time.sleep(delay)


def get_dns_ip(manifest: "Manifest") -> str:
    """
    Reserved by AWS. The IP address of the DNS server is the base of the VPC network range plus two.
    For VPCs with multiple CIDR blocks, the IP address of the DNS server is located in the primary CIDR.
    We also reserve the base of each subnet range plus two for all CIDR blocks in the VPC.
    """
    if manifest.vpc.cidr_block is None:
        manifest.vpc.fillup_from_ssm()
    if manifest.vpc.cidr_block is None:
        manifest.vpc.fetch_properties()
    if manifest.vpc.cidr_block is None:
        raise ValueError("Impossible to localize the VPC CIDR Block!")
    base: str = manifest.vpc.cidr_block[:-3]
    return str(ipaddress.ip_address(base) + 2)


def get_dns_ip_cidr(manifest: "Manifest") -> str:
    """
    Reserved by AWS. The IP address of the DNS server is the base of the VPC network range plus two.
    For VPCs with multiple CIDR blocks, the IP address of the DNS server is located in the primary CIDR.
    We also reserve the base of each subnet range plus two for all CIDR blocks in the VPC.
    """
    cidr: str = f"{get_dns_ip(manifest)}/32"
    _logger.debug("DNS CIDR: %s", cidr)
    return cidr


def print_dir(dir: str) -> None:
    for dirname, dirnames, filenames in os.walk(dir):
        # print path to all subdirectories first.
        for subdirname in dirnames:
            _logger.debug(os.path.join(dirname, subdirname))
        # print path to all filenames.
        for filename in filenames:
            _logger.debug((os.path.join(dirname, filename)))


def resolve_parameters(template: str, parameters: Dict[str, str]) -> str:
    string_template = Template(template)
    template = string_template.safe_substitute(parameters)
    return template
