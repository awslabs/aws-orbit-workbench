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

import os
import pytest
from typing import Optional

from kubernetes import config
from custom_resources import PodDefault

MANIFESTS_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "manifests",
)

@pytest.mark.order(2)
@pytest.mark.namespace(create=False)
def test_poddefault_1(kube):

    poddefault = PodDefault.load(os.path.join(MANIFESTS_PATH, "poddefault.yaml"))
    poddefault.create(namespace="orbit-system")
    assert poddefault.name is not None
    poddefault.delete()


@pytest.mark.order(1)
@pytest.mark.namespace(create=False)
def test_poddefault_2(kube):
    body = {
        "apiVersion": "kubeflow.org/v1alpha1",
        "kind": "PodDefault",
        "metadata": {
            "name": "orbit-stuff-2"
        },
        "spec": {"selector": {"matchLabels": {f"orbit/stuff": ""}}, "desc": "Orbit Stuff"},
    }

    poddefault = PodDefault(body)
    poddefault.create(namespace="orbit-system")
    poddefault.delete()