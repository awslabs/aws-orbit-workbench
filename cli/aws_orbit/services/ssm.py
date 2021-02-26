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

import json
import logging
from typing import Any, Dict, List, Optional, cast

from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)


def put_parameter(name: str, obj: Dict[str, Any]) -> None:
    client = boto3_client(service_name="ssm")
    client.put_parameter(
        Name=name,
        Value=str(json.dumps(obj=obj, sort_keys=True)),
        Overwrite=True,
        Tier="Intelligent-Tiering",
        Type="String",
    )


def get_parameter(name: str) -> Dict[str, Any]:
    client = boto3_client(service_name="ssm")
    json_str: str = client.get_parameter(Name=name)["Parameter"]["Value"]
    return cast(Dict[str, Any], json.loads(json_str))


def get_parameter_if_exists(name: str) -> Optional[Dict[str, Any]]:
    client = boto3_client(service_name="ssm")
    try:
        json_str: str = client.get_parameter(Name=name)["Parameter"]["Value"]
    except client.exceptions.ParameterNotFound:
        return None
    return cast(Dict[str, Any], json.loads(json_str))


def does_parameter_exist(name: str) -> bool:
    client = boto3_client(service_name="ssm")
    try:
        client.get_parameter(Name=name)
        return True
    except client.exceptions.ParameterNotFound:
        return False


def list_parameters(prefix: str) -> List[str]:
    client = boto3_client(service_name="ssm")
    paginator = client.get_paginator("describe_parameters")
    response_iterator = paginator.paginate(
        ParameterFilters=[
            {
                "Key": "Type",
                "Option": "Equals",
                "Values": [
                    "String",
                ],
            },
            {"Key": "Name", "Option": "BeginsWith", "Values": [prefix]},
        ],
    )
    ret: List[str] = []
    for page in response_iterator:
        for par in page.get("Parameters"):
            ret.append(par["Name"])
    return ret


def delete_parameters(parameters: List[str]) -> None:
    if parameters:
        client = boto3_client(service_name="ssm")
        client.delete_parameters(Names=parameters)


def cleanup_env(env_name: str, top_level: str = "orbit") -> None:
    pars: List[str] = [p for p in list_parameters(prefix=f"/{top_level}/{env_name}/") if p.endswith("/cicd") is False]
    delete_parameters(parameters=pars)


def cleanup_teams(env_name: str, top_level: str = "orbit") -> None:
    pars: List[str] = list_parameters(prefix=f"/{top_level}/{env_name}/teams/")
    delete_parameters(parameters=pars)


def cleanup_by_suffix(env_name: str, suffix: str, top_level: str = "orbit") -> None:
    pars: List[str] = [p for p in list_parameters(prefix=f"/{top_level}/{env_name}/") if p.endswith(suffix)]
    delete_parameters(parameters=pars)


def cleanup_manifest(env_name: str, top_level: str = "orbit") -> None:
    cleanup_by_suffix(env_name=env_name, suffix="/manifest", top_level=top_level)


def cleanup_context(env_name: str, top_level: str = "orbit") -> None:
    cleanup_by_suffix(env_name=env_name, suffix="/context", top_level=top_level)


def cleanup_changeset(env_name: str, top_level: str = "orbit") -> None:
    cleanup_by_suffix(env_name=env_name, suffix="/changeset", top_level=top_level)


def list_teams_contexts(env_name: str, top_level: str = "orbit") -> List[str]:
    return [p for p in list_parameters(prefix=f"/{top_level}/{env_name}/teams/") if p.endswith("/context")]
