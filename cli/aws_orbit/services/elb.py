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
from pprint import pformat
from typing import Any, Dict, List

from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def _tags2dict(tags: List[Dict[str, str]]) -> Dict[str, str]:
    return {x["Key"]: x["Value"] for x in tags}


def _check_elb_tag(env_name: str, tags: Dict[str, str]) -> bool:
    key: str = f"kubernetes.io/cluster/orbit-{env_name}"
    return tags.get(key) == "owned"


def _apply_tag_filter(env_name: str, elbs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    names: List[str] = [x["LoadBalancerName"] for x in elbs]
    _logger.debug("Filtering ELBS:\n%s", pformat(names))
    if not names:
        return []
    client = boto3_client("elb")
    res: List[Dict[str, Any]] = client.describe_tags(LoadBalancerNames=names)["TagDescriptions"]
    tags: Dict[str, Dict[str, str]] = {x["LoadBalancerName"]: _tags2dict(tags=x["Tags"]) for x in res}
    return [x for x in elbs if _check_elb_tag(env_name=env_name, tags=tags[x["LoadBalancerName"]])]


def describe_load_balancers(env_name: str) -> List[Dict[str, Any]]:
    paginator = boto3_client("elb").get_paginator("describe_load_balancers")
    elbs: List[Dict[str, Any]] = []
    for page in paginator.paginate():
        _logger.debug(page)
        elbs += _apply_tag_filter(env_name=env_name, elbs=page.get("LoadBalancerDescriptions", []))
    _logger.debug("Filtered ELB names:\n%s", pformat([x["LoadBalancerName"] for x in elbs]))
    return elbs


def identify_services(names: List[str]) -> Dict[str, str]:
    if not names:
        return {}
    client = boto3_client("elb")
    res: List[Dict[str, Any]] = client.describe_tags(LoadBalancerNames=names)["TagDescriptions"]
    tags: Dict[str, Dict[str, str]] = {x["LoadBalancerName"]: _tags2dict(tags=x["Tags"]) for x in res}
    services = {t["kubernetes.io/service-name"]: name for name, t in tags.items() if "kubernetes.io/service-name" in t}
    _logger.debug("Services itentified for each ELB:\n%s", pformat(services))
    return services


def _search_elb_by_name(elbs: List[Dict[str, Any]], name: str) -> Dict[str, Any]:
    for elb in elbs:
        if elb["LoadBalancerName"] == name:
            return elb
    raise RuntimeError(f"ELB {name} not found!")


def get_elbs_by_service(env_name: str) -> Dict[str, Dict[str, Any]]:
    # Cleaning up CreatedTime cause datatime objects are not JSON serializable
    elbs = [
        {
            k: v
            for k, v in x.items()
            if k
            not in {
                "CreatedTime",
                "HealthCheck",
                "CanonicalHostedZoneNameID",
                "CanonicalHostedZoneName",
                "BackendServerDescriptions",
            }
        }
        for x in describe_load_balancers(env_name=env_name)
    ]
    services = identify_services(names=[x["LoadBalancerName"] for x in elbs])
    return {s: _search_elb_by_name(elbs=elbs, name=a) for s, a in services.items()}


def delete_load_balancers(env_name: str) -> None:
    client = boto3_client("elb")
    for elb in describe_load_balancers(env_name=env_name):
        client.delete_load_balancer(LoadBalancerName=elb["LoadBalancerName"])
