#!/usr/bin/env python

import json
import logging
import os
import subprocess
from typing import Dict

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_secret() -> Dict[str, Dict[str, str]]:
    env = os.environ.get("AWS_ORBIT_ENV")
    secret_name = f"orbit-{env}-docker-credentials"
    region_name = os.environ.get("AWS_DEFAULT_REGION")

    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logger.exception(e)
        return {}
    else:
        return json.loads(get_secret_value_response.get("SecretString", "{}"))


if __name__ == "__main__":
    credentials = get_secret()
    for registry, creds in credentials.items():
        username = creds["username"]
        password = creds["password"]
        subprocess.call(
            f"docker login --username {username} --password '{password}' {registry}",
            shell=True,
        )
