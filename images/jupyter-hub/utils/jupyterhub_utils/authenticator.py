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
from typing import Any, Dict, Tuple, cast

import boto3
from jupyterhub.auth import Authenticator
from tornado.httpclient import HTTPError
from tornado.log import app_log
from tornado.web import RequestHandler

from jupyterhub_utils.ssm import ENV_NAME


class OrbitWorkbenchAuthenticator(Authenticator):  # type: ignore
    def authenticate(self, handler: RequestHandler, data: Dict[str, str]) -> Any:
        app_log.info("data: %s", data)
        if handler.request.uri is None:
            app_log.error("Empty URI")
            return
        token: str = self._get_token(url=handler.request.uri)
        response: Dict[str, Any] = boto3.client("lambda").invoke(
            FunctionName=f"orbit-{ENV_NAME}-token-validation",
            InvocationType="RequestResponse",
            Payload=json.dumps({"token": token}).encode("utf-8"),
        )

        if response is None:
            app_log.error(f"Invalid Lambda response:\n{response}")
            return

        app_log.info("claims: %s", response)
        if "cognito:username" not in response or response.get("cognito:username") is None:
            if "errorMessage" in response:
                app_log.error(f"Failed authentication with error: {response['errorMessage']}")
                return
            else:
                app_log.error(f"Failed authentication with unknown return: {response}")
                return
        return cast(str, response["cognito:username"])

    async def refresh_user(self, user, handler=None):
        """Refresh auth data for a given user

        Allows refreshing or invalidating auth data.

        Only override if your authenticator needs
        to refresh its data about users once in a while.

        .. versionadded: 1.0

        Args:
         user (User): the user to refresh
         handler (tornado.web.RequestHandler or None): the current request handler
        Returns:
         auth_data (bool or dict):
             Return **True** if auth data for the user is up-to-date
             and no updates are required.

             Return **False** if the user's auth data has expired,
             and they should be required to login again.

             Return a **dict** of auth data if some values should be updated.
             This dict should have the same structure as that returned
             by :meth:`.authenticate()` when it returns a dict.
             Any fields present will refresh the value for the user.
             Any fields not present will be left unchanged.
             This can include updating `.admin` or `.auth_state` fields.
        """

        auth_state = yield user.get_auth_state()

        response: Dict[str, Any] = boto3.client("lambda").invoke(
            FunctionName=f"orbit-{ENV_NAME}-token-validation"
            InvocationType="RequestResponse",
            Payload=json.dumps({"token": auth_state['access_token']}).encode("utf-8"),
        )

        if response is None:
            app_log.error(f"Invalid Lambda response:\n{response}")
            return False

        app_log.info("claims: %s", response)
            if "cognito:username" not in response or response.get("cognito:username") is None:
                if "errorMessage" in response:
                    app_log.error(f"Failed authentication with error: {response['errorMessage']}")
                    return False
                else:
                    app_log.error(f"Failed authentication with unknown return: {response}")
                    return False

        if response is None:
            return False

        return True

    @staticmethod
    def _get_token(url: str) -> str:
        app_log.info("url: %s", url)
        parts: Tuple[str, ...] = tuple(url.split(sep="/login?next=%2Fhub%2Fhome&id_token=", maxsplit=1))
        if len(parts) != 2:
            app_log.error("url:\n%s", url)
            raise HTTPError(500, f"url: {url}")
        return parts[1]
