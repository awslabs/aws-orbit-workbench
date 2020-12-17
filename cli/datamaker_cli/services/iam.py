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
from typing import Any, Dict, Optional, cast

from datamaker_cli.manifest import Manifest

_logger: logging.Logger = logging.getLogger(__name__)


def get_open_id_connect_provider(manifest: Manifest, open_id_connect_provider_id: str) -> Optional[Dict[str, Any]]:
    open_id_connect_provider_arn = f"arn:aws:iam::{manifest.account_id}:oidc-provider/{open_id_connect_provider_id}"
    _logger.debug(f"Getting OpenIDConnectProvider: {open_id_connect_provider_arn}")

    iam_client = manifest.boto3_client("iam")
    try:
        return cast(
            Dict[str, Any],
            iam_client.get_open_id_connect_provider(OpenIDConnectProviderArn=open_id_connect_provider_arn),
        )
    except iam_client.exceptions.NoSuchEntityException:
        return None
