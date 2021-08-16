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

import kopf
import logging
from typing import Any, Dict

from kubernetes import dynamic
from kubernetes.dynamic import exceptions as k8s_exceptions
from orbit_controller import ORBIT_API_GROUP, ORBIT_API_VERSION, dynamic_client
from urllib3.exceptions import ReadTimeoutError


@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_) -> None:
    settings.admission.server = kopf.WebhookServer(
        cafile="/certs/ca.crt",
        certfile="/certs/tls.crt",
        pkeyfile="/certs/tls.key",
        port=443
    )
    settings.posting.level = logging.DEBUG


@kopf.index("namespaces")
def namespaces_idx(name: str, body: kopf.Body, logger: kopf.Logger, **_) -> Dict[str, str]:
    logger.debug("Indexing namespace: %s", name)
    return {name: body}


@kopf.on.mutate("pods", id="update-pod-images")
def update_pod_images(spec: kopf.Spec, patch: kopf.Patch, namespace: str, namespaces_idx: kopf.Index, logger: kopf.Logger, **kwargs) -> Dict[str, Any]:
    ns = namespaces_idx.get(namespace, [])
    logger.debug("namespace: %s - %s", namespace, ns)
    pass


@kopf.on.resume("imagereplications")
@kopf.on.create("imagereplications")
def 