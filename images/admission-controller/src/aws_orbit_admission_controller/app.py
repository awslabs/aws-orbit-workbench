import http
import os
from typing import Any

from aws_orbit_admission_controller.namespace import process_request as process_namespace_request
from aws_orbit_admission_controller.pod import process_request as process_pod_request
from flask import Flask, request
import random

app = Flask(__name__)
app.logger.info("environ: %s", os.environ)


@app.route("/namespace", methods=["POST"])
def namespace() -> Any:
    # See here for AdmissionReview request/response
    # https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#request
    return process_namespace_request(logger=app.logger, request=request.json["request"])


@app.route("/pod", methods=["POST"])
def pod() -> Any:
    # See here for AdmissionReview request/response
    # https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#request
    return process_pod_request(logger=app.logger, request=request.json["request"])


@app.route("/health", methods=["GET"])
def health() -> Any:
    app.logger.debug("Health check")
    return ("", http.HTTPStatus.NO_CONTENT)

@app.route('/hello')
def hello():
    r = random.randint(0, 1000)
    return f'Hello! random number gen: {r}'

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, use_reloader=True)  # pragma: no cover
