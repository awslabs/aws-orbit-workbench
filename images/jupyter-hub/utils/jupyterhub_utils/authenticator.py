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

from typing import Any, Dict, Tuple, Union, cast

from jupyterhub.auth import Authenticator
from jupyterhub_utils.cognito import get_claims
from tornado.log import app_log
from tornado.web import RequestHandler


class DataMakerAuthenticator(Authenticator):  # type: ignore
    def authenticate(self, handler: RequestHandler, data: Dict[str, str]) -> Any:
        app_log.info("data: %s", data)
        if handler.request.uri is None:
            raise RuntimeError("Empty URI.")
        token: str = self._get_token(url=handler.request.uri)
        claims: Dict[str, Union[str, int]] = get_claims(token=token)
        app_log.info("claims: %s", claims)
        return cast(str, claims["cognito:username"])

    @staticmethod
    def _get_token(url: str) -> str:
        app_log.info("url: %s", url)
        parts: Tuple[str, ...] = tuple(url.split(sep="/login?next=%2Fhub%2Fhome&token=", maxsplit=1))
        if len(parts) != 2:
            raise RuntimeError(f"url: {url}")
        return parts[1]
