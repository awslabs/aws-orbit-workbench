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


import base64
import json
import logging
import os
from typing import Any, Dict, cast, List, Union, Optional
from urllib.parse import urlparse, urlencode

import jwt
import requests
import time
from aws_orbit_admission_controller import get_client
from flask import Flask, render_template, request, jsonify
from jose import jwk, jwt
from jose.utils import base64url_decode
from kubernetes import dynamic

_cognito_keys: Optional[List[Dict[str, str]]] = None


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

    groups = _get_user_groups_from_jwt(logger)

    ready = _is_profile_ready_for_user(logger, username, email)
    logger.debug("user space is READY? %s", ready)

    client_id, cognito_domain, hostname, logout_uri = get_logout_url(logger)
    env_name = os.environ['ENV_NAME']
    return render_template('index.html', title='login',
                           username=username, hostname=hostname,
                           logout_uri=logout_uri, client_id=client_id,
                           cognito_domain=cognito_domain,
                           teams=groups,
                           env_name=env_name)


def get_logout_url(logger):
    base_url = request.base_url
    hostname = urlparse(base_url).hostname
    client_id = os.environ['COGNITO_APP_CLIENT_ID']
    logger.debug('clientid=%s', client_id)
    cognito_domain = os.environ['COGNITO_DOMAIN']
    logout_uri = f"https://{hostname}/orbit/logout"
    params = {'logout_uri': logout_uri, 'client_id': client_id}
    param_str = urlencode(params)
    logout_redirect_url = f"https://{os.environ['COGNITO_DOMAIN']}/logout?{param_str}"
    logger.debug("logout url: %s", logout_redirect_url)
    return client_id, cognito_domain, hostname, logout_uri


def logout(logger: logging.Logger, app: Flask) -> Any:
    return render_template('logout.html', title='Orbit Session ended')


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
    logger.debug("encoded_jwt 'x-amzn-oidc-data':\n %s", encoded_jwt)
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


def _get_user_groups_from_jwt(logger):
    logger.debug("headers: %s", json.dumps(dict(request.headers)))
    encoded_jwt = request.headers['X-Amzn-Oidc-Accesstoken']
    logger.debug("encoded_jwt 'X-Amzn-Oidc-Accesstoken':\n %s", encoded_jwt)
    claims = get_claims(logger, encoded_jwt)
    groups = claims['cognito:groups'] if 'cognito:groups' in claims else []
    return groups


def _get_keys(logger) -> List[Dict[str, str]]:
    global _cognito_keys
    region = os.environ['AWS_REGION']
    user_pool_id = os.environ['COGNITO_USERPOOL_ID']
    if _cognito_keys is None:
        logger.debug("Fetching keys...")
        url: str = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
        _cognito_keys = cast(List[Dict[str, str]], requests.get(url).json()["keys"])
    return _cognito_keys


def get_claims(logger, token: str) -> Dict[str, Union[str, int]]:
    client_id = os.environ['COGNITO_APP_CLIENT_ID']
    # get the kid from the headers prior to verification
    headers: Dict[str, str] = cast(Dict[str, str], jwt.get_unverified_headers(token=token))
    kid: str = headers["kid"]
    # search for the kid in the downloaded public keys
    for key in _get_keys(logger):
        if kid == key["kid"]:
            # construct the public key
            public_key = jwk.construct(key_data=key)
            break
    else:
        raise ValueError("Public key not found in JWK.")
    # get the last two sections of the token,
    # message and signature (encoded in base64)
    message, encoded_signature = token.rsplit(".", 1)
    # decode the signature
    decoded_signature: bytes = base64url_decode(encoded_signature.encode("utf-8"))
    # verify the signature
    if public_key.verify(msg=message.encode("utf8"), sig=decoded_signature) is False:
        raise RuntimeError("Signature verification failed.")
    logger.debug("Signature validaded.")
    # since we passed the verification, we can now safely use the unverified claims
    claims: Dict[str, Union[str, int]] = cast(Dict[str, Union[str, int]], jwt.get_unverified_claims(token))
    # additionally we can verify the token expiration
    if time.time() > int(claims["exp"]):
        raise ValueError("Token expired.")
    logger.debug("Token not expired.")
    logger.debug("claims: %s", claims)

    return claims
