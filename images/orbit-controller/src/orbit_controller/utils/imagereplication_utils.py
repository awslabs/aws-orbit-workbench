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
import re
from typing import Any, Dict, Optional, Tuple, Union

import boto3
import kopf
import yaml
from kubernetes import dynamic
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION


def _generate_buildspec(repo_host: str, repo_prefix: str, src: str, dest: str) -> Dict[str, Any]:
    repo = dest.replace(f"{repo_host}/", "").split(":")[0]
    build_spec = {
        "version": 0.2,
        "phases": {
            "install": {
                "runtime-versions": {"python": 3.7, "docker": 19},
                "commands": [
                    (
                        "nohup /usr/sbin/dockerd --host=unix:///var/run/docker.sock "
                        "--host=tcp://0.0.0.0:2375 --storage-driver=overlay&"
                    ),
                    'timeout 15 sh -c "until docker info; do echo .; sleep 1; done"',
                ],
            },
            "pre_build": {
                "commands": [
                    "/var/scripts/retrieve_docker_creds.py && echo 'Docker logins successful' "
                    "|| echo 'Docker logins failed'",
                    f"aws ecr get-login-password | docker login --username AWS --password-stdin {repo_host}",
                    (
                        f"aws ecr create-repository --repository-name {repo} "
                        f"--tags Key=Env,Value={repo_prefix} || echo 'Already exists'"
                    ),
                ]
            },
            "build": {"commands": [f"docker pull {src}", f"docker tag {src} {dest}", f"docker push {dest}"]},
        },
    }
    return build_spec


def _patch_imagereplication(
    namespace: str,
    name: str,
    patch: Dict[str, Any],
    client: dynamic.DynamicClient,
    logger: Union[kopf.Logger, logging.Logger],
) -> None:
    api = client.resources.get(group=ORBIT_API_GROUP, api_version=ORBIT_API_VERSION, kind="ImageReplication")
    logger.debug("Patching %s/%s with %s", namespace, name, patch)
    api.patch(namespace=namespace, name=name, body=patch, content_type="application/merge-patch+json")


def get_config() -> Dict[str, Any]:
    config = {
        "repo_host": os.environ.get("REPO_HOST", ""),
        "repo_prefix": os.environ.get("REPO_PREFIX", ""),
        "codebuild_project": os.environ.get("CODEBUILD_PROJECT", ""),
        "codebuild_timeout": int(os.environ.get("CODEBUILD_TIMEOUT", "30")),
        "codebuild_image": os.environ.get("ORBIT_CODEBUILD_IMAGE", ""),
        "replicate_external_repos": os.environ.get("REPLICATE_EXTERNAL_REPOS", "False").lower() in ["true", "yes", "1"],
        "workers": int(os.environ.get("WORKERS", "4")),
        "max_replication_attempts": int(os.environ.get("MAX_REPLICATION_ATTEMPTS", "3")),
    }
    return config


def replicate_image(src: str, dest: str, config: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    buildspec = yaml.safe_dump(_generate_buildspec(config["repo_host"], config["repo_prefix"], src, dest))

    try:
        client = boto3.client("codebuild")
        build_id = client.start_build(
            projectName=config["codebuild_project"],
            sourceTypeOverride="NO_SOURCE",
            buildspecOverride=buildspec,
            timeoutInMinutesOverride=config["codebuild_timeout"],
            privilegedModeOverride=True,
            imageOverride=config["codebuild_image"],
        )["build"]["id"]
        return build_id, None
    except Exception as e:
        return None, str(e)


def get_desired_image(image: str, config: Dict[str, Any]) -> str:
    external_ecr_match = re.compile(r"^[0-9]{12}\.dkr\.ecr\..+\.amazonaws.com/")
    public_ecr_match = re.compile(r"^public.ecr.aws/.+/")

    if image.startswith(config["repo_host"]):
        return image
    elif external_ecr_match.match(image):
        if config["replicate_external_repos"]:
            return external_ecr_match.sub(
                f"{config['repo_host']}/{config['repo_prefix']}/", image.replace("@sha256", "")
            )
        else:
            return image
    elif public_ecr_match.match(image):
        return public_ecr_match.sub(f"{config['repo_host']}/{config['repo_prefix']}/", image.replace("@sha256", ""))
    else:
        return f"{config['repo_host']}/{config['repo_prefix']}/{image.replace('@sha256', '')}"


def create_imagereplication(
    namespace: str,
    source: str,
    destination: str,
    client: dynamic.DynamicClient,
    logger: Union[kopf.Logger, logging.Logger],
) -> Tuple[str, str]:
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="ImageReplication")
    imagereplication = {
        "apiVersion": f"{ORBIT_API_GROUP}/{ORBIT_API_VERSION}",
        "kind": "ImageReplication",
        "metadata": {
            "generateName": "image-replication-",
        },
        "spec": {"destination": destination, "source": source},
    }
    result = api.create(namespace=namespace, body=imagereplication).to_dict()
    logger.debug("Created ImageReplication: %s", result)
    metadata = result.get("metadata", {})
    return metadata.get("namespace", None), metadata.get("name", None)


def image_replicated(image: str, logger: Union[kopf.Logger, logging.Logger]) -> bool:
    try:
        repo, tag = image.split(":")
        repo = "/".join(repo.split("/")[1:])
        client = boto3.client("ecr")
        paginator = client.get_paginator("list_images")
        for page in paginator.paginate(repositoryName=repo):
            for imageId in page["imageIds"]:
                if imageId.get("imageTag", None) == tag:
                    logger.info("ECR Repository contains Image: %s", image)
                    return True
        logger.debug("Tag %s not found in ECR Repository %s", tag, repo)
        return False
    except Exception as e:
        logger.warn(str(e))
        return False


def update_imagereplication_status(
    namespace: str,
    name: str,
    status: Dict[str, str],
    client: dynamic.DynamicClient,
    logger: Union[kopf.Logger, logging.Logger],
) -> None:
    _patch_imagereplication(
        namespace=namespace,
        name=name,
        client=client,
        logger=logger,
        patch={"status": status},
    )
