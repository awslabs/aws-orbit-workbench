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
from typing import Any, Dict, Tuple, Union, cast

import boto3
from jupyterhub.auth import Authenticator
from tornado.log import app_log
from tornado.web import RequestHandler

from jupyterhub_utils.ssm import ENV_NAME


class Orbit WorkbenchAuthenticator(Authenticator):  # type: ignore
    def authenticate(self, handler: RequestHandler, data: Dict[str, str]) -> Any:
        app_log.info("data: %s", data)
        if handler.request.uri is None:
            raise RuntimeError("Empty URI.")
        token: str = self._get_token(url=handler.request.uri)
        response: Dict[str, Any] = boto3.client("lambda").invoke(
            FunctionName=f"orbit-{ENV_NAME}-token-validation",
            InvocationType="RequestResponse",
            Payload=json.dumps({"token": token}).encode("utf-8"),
        )
        if response.get("StatusCode") != 200 or response.get("Payload") is None:
            raise RuntimeError(f"Invalid Lambda response:\n{response}")
        claims: Dict[str, Union[str, int]] = json.loads(response["Payload"].read().decode("utf-8"))
        app_log.info("claims: %s", claims)
        if "cognito:username" not in claims or claims.get("cognito:username") is None:
            raise RuntimeError(f"Invalid claims:\n{claims}")
        return cast(str, claims["cognito:username"])

    @staticmethod
    def _get_token(url: str) -> str:
        app_log.info("url: %s", url)
        parts: Tuple[str, ...] = tuple(url.split(sep="/login?next=%2Fhub%2Fhome&token=", maxsplit=1))
        if len(parts) != 2:
            raise RuntimeError(f"url: {url}")
        return parts[1]
