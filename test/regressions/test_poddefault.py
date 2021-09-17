import pytest
from typing import Optional

from kubernetes import config
from custom_resources import PodDefault


@pytest.mark.order(2)
@pytest.mark.namespace(create=False)
def test_poddefault_1(kube):
    body = {
        "apiVersion": "kubeflow.org/v1alpha1",
        "kind": "PodDefault",
        "metadata": {
            "name": "orbit-stuff-1"
        },
        "spec": {"selector": {"matchLabels": {f"orbit/stuff": ""}}, "desc": "Orbit Stuff"},
    }

    poddefault = PodDefault(body)
    poddefault.create(namespace="orbit-system")
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