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
from typing import Any, Dict, List, Optional, Union, cast

import requests
from jose import jwk, jwt
from jose.utils import base64url_decode

logger = logging.getLogger()
logger.setLevel(logging.INFO)

COGNITO_USER_POOL_ID: str = os.environ["COGNITO_USER_POOL_ID"]
COGNITO_USER_POOL_CLIENT_ID: str = os.environ["COGNITO_USER_POOL_CLIENT_ID"]
REGION: str = os.environ["REGION"]

_cognito_keys: Optional[List[Dict[str, str]]] = None


def _get_keys() -> List[Dict[str, str]]:
    global _cognito_keys
    if _cognito_keys is None:
        print("Fetching keys...")
        url: str = f"https://cognito-idp.{REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        _cognito_keys = cast(List[Dict[str, str]], requests.get(url).json()["keys"])
    return _cognito_keys


def get_claims(token: str) -> Dict[str, Union[str, int]]:
    # get the kid from the headers prior to verification
    headers: Dict[str, str] = cast(Dict[str, str], jwt.get_unverified_headers(token=token))
    kid: str = headers["kid"]
    # search for the kid in the downloaded public keys
    for key in _get_keys():
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
    print("Signature validaded.")
    # since we passed the verification, we can now safely use the unverified claims
    claims: Dict[str, Union[str, int]] = cast(Dict[str, Union[str, int]], jwt.get_unverified_claims(token))
    # additionally we can verify the token expiration
    if time.time() > int(claims["exp"]):
        raise ValueError("Token expired.")
    print("Token not expired.")
    # and the Audience (use claims['client_id'] if verifying an access token)
    if claims["aud"] != COGNITO_USER_POOL_CLIENT_ID:
        raise ValueError("Token was not issued for this audience.")
    # now we can use the claims
    return claims


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Union[str, int]]:
    claims: Dict[str, Union[str, int]] = get_claims(token=event["token"])
    logger.info("claims: %s", claims)
    return claims
