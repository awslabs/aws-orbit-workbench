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

import http
import os
import random
from typing import Any

from aws_orbit_admission_controller.pod import process_request as process_pod_request
from flask import Flask, request,jsonify
from flask import render_template

from aws_orbit_admission_controller.home import login,logout

# from flask_cognito import cognito_auth_required, current_user, current_cognito_jwt


app = Flask(__name__, static_url_path='/static')
app.logger.info("environ: %s", os.environ)

# if "COGNITO_USERPOOL_ID" in os.environ:
#     app.logger.info("initiate cognito session with user pool id %s", os.environ['COGNITO_USERPOOL_ID'])
#     app.config.extend({
#         'COGNITO_REGION': os.environ['AWS_REGION'],
#         'COGNITO_USERPOOL_ID':  os.environ['COGNITO_USERPOOL_ID'],
#         # optional
#         'COGNITO_APP_CLIENT_ID': os.environ['COGNITO_APP_CLIENT_ID'],  # client ID you wish to verify user is authenticated against
#         'COGNITO_CHECK_TOKEN_EXPIRATION': True,  # disable token expiration checking for testing purposes
#         'COGNITO_JWT_HEADER_NAME': os.environ['COGNITO_JWT_HEADER_NAME'],
#         'COGNITO_JWT_HEADER_PREFIX': os.environ['COGNITO_JWT_HEADER_PREFIX']
#     })

@app.route("/pod", methods=["POST"])
def pod() -> Any:
    # See here for AdmissionReview request/response
    # https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#request
    return process_pod_request(logger=app.logger, request=request.json["request"])


@app.route("/health", methods=["GET"])
def health() -> Any:
    return ("", http.HTTPStatus.NO_CONTENT)


@app.route("/hello")
def hello() -> Any:
    r = random.randint(0, 1000)
    return f"Hello! random number gen: {r}"

@app.route("/login")
# @cognito_auth_required
def login_request() -> Any:
    return login(logger=app.logger, app=app)
    # user must have valid cognito access or ID token in header
    # (accessToken is recommended - not as much personal information contained inside as with idToken)
    # return jsonify({
    #     'cognito_username': current_cognito_jwt['username']   # from cognito pool
    # })

@app.route("/logout")
def logout_request() -> Any:
    return logout(logger=app.logger,app=app)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, use_reloader=True)  # pragma: no cover
