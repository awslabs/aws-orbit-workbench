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
from flask import Flask, request

app = Flask(__name__)
app.logger.info("environ: %s", os.environ)


@app.route("/pod", methods=["POST"])
def pod() -> Any:
    # See here for AdmissionReview request/response
    # https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#request
    return process_pod_request(logger=app.logger, request=request.json["request"])


@app.route("/health", methods=["GET"])
def health() -> Any:
    return ("", http.HTTPStatus.NO_CONTENT)


@app.route("/hello", methods=["GET", "POST"])
def hello() -> Any:
    r = random.randint(0, 1000)
    return f"Hello! random number gen: {r}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, use_reloader=True)  # pragma: no cover
