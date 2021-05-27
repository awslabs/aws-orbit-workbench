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


from typing import Any, Dict, Optional, cast
from flask import Flask, render_template,request
import logging
import json
import jwt
import requests
import base64
import os

def login(logger: logging.Logger, app: Flask) -> Any:
    logger.debug("cookies: %s", json.dumps(request.cookies))
    return render_template('index.html', title='login')

def logout(logger: logging.Logger, app: Flask) -> Any:
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
    logger.debug("payload:\n %s",payload)
    username = payload['username']
    email = payload['email']
    logger.debug("username: %s, email: email", payload)


    return render_template('index.html', title='logout')