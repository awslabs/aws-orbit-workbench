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


from typing import Any, Dict, Optional, cast,List
from flask import Flask, render_template,request,jsonify
from kubernetes.client import CoreV1Api, V1ConfigMap
from kubernetes.dynamic import exceptions as k8s_exceptions
from aws_orbit_admission_controller import get_client
from kubernetes import dynamic
import logging
import json
import jwt
import requests
import base64
import os


def is_ready(logger: logging.Logger, app: Flask) -> Any:
    logger.debug("cookies: %s", json.dumps(request.cookies))
    email, username = _get_user_info_from_jwt(logger)

    ready = _is_profile_ready_for_user(logger, username, email)
    logger.debug("username: %s, email: %s", username, email)
    return jsonify({"isReady": ready})


def login(logger: logging.Logger, app: Flask) -> Any:
    logger.debug("cookies: %s", json.dumps(request.cookies))
    email, username = _get_user_info_from_jwt(logger)
    logger.debug("username: %s, email: %s", username, email)

    ready = _is_profile_ready_for_user(logger, username, email)
    logger.debug("user space is READY? %s", ready)
    title = f'Welcome to Orbit Workbench'
    return render_template('index.html', title='login', username=username)


def logout(logger: logging.Logger, app: Flask) -> Any:
    return render_template('index.html', title='logout')


def _is_profile_ready_for_user(logger: logging.Logger, username: str, email: str):
    profiles = _get_kf_profiles(get_client())
    for p in profiles:
        logger.debug('profile %s', json.dumps(p))
        owner = p["spec"].get("owner", {})
        logger.debug('owner %s', json.dumps(owner))
        user_email = owner.get('name', None)
        if user_email and user_email == email:
            return True
    return False


def _get_kf_profiles(client: dynamic.DynamicClient) -> List[Dict[str, Any]]:
    try:
        api = client.resources.get(api_version='v1', group="kubeflow.org", kind="Profile")
        profiles = api.get()
        return cast(List[Dict[str, Any]], profiles.to_dict().get("items", []))
    except dynamic.exceptions.ResourceNotFoundError:
        return []


# https://docs.aws.amazon.com/elasticloadbalancing/latest/application/listener-authenticate-users.html
def _get_user_info_from_jwt(logger):
    logger.debug("headers: %s", json.dumps(dict(request.headers)))
    encoded_jwt = request.headers['x-amzn-oidc-data']
    jwt_headers = encoded_jwt.split('.')[0]
    decoded_jwt_headers = base64.b64decode(jwt_headers)
    decoded_jwt_headers = decoded_jwt_headers.decode("utf-8")
    decoded_json = json.loads(decoded_jwt_headers)
    kid = decoded_json['kid']
    region = os.environ['AWS_REGION']
    # Step 2: Get the public key from regional endpoint
    url = 'https://public-keys.auth.elb.' + region + '.amazonaws.com/' + kid
    req = requests.get(url)
    pub_key = req.text
    # Step 3: Get the payload
    payload = jwt.decode(encoded_jwt, pub_key, algorithms=['ES256'])
    logger.debug("payload:\n %s", payload)
    username = payload['username']
    email = payload['email']
    return email, username