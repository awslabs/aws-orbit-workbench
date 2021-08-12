import logging
import time
from typing import Any, Dict, List, cast

from kubernetes import config
from kubernetes.client import AppsV1Api, CoreV1Api, NetworkingV1beta1Api, NetworkingV1beta1IngressList, V1Service

_logger: logging.Logger = logging.getLogger(__name__)


def get_service_hostname(name: str, k8s_context: str, namespace: str = "default") -> str:
    config.load_kube_config(context=k8s_context)
    v1 = CoreV1Api()
    while True:
        resp = cast(V1Service, v1.read_namespaced_service_status(name=name, namespace=namespace))
        status: Dict[str, Any] = resp.status.to_dict()
        if "load_balancer" in status:
            if "ingress" in status["load_balancer"]:
                if status["load_balancer"]["ingress"]:
                    if "hostname" in status["load_balancer"]["ingress"][0]:
                        break
        time.sleep(10)
    return str(status["load_balancer"]["ingress"][0]["hostname"])


def get_service_addresses(name: str, k8s_context: str, namespace: str = "orbit-system") -> List[Dict[str, Any]]:
    _logger.debug("Retrieving Endpoints for Service %s in Namespace %s", name, namespace)
    config.load_kube_config(context=k8s_context)
    v1 = CoreV1Api()
    result = []
    for attempt in range(10):
        time.sleep(60)
        resp = v1.read_namespaced_endpoints(name=name, namespace=namespace)
        endpoints = resp.to_dict()
        subsets = endpoints.get("subsets")
        if subsets and len(subsets) > 0:
            _logger.debug("Endpoint Subsets: %s", subsets)

            addresses = None
            for subset in subsets:
                addresses = subset.get("addresses")
                if addresses and len(addresses) > 0:
                    result.extend(addresses)

            if addresses and len(addresses) > 0:
                return cast(List[Dict[str, Any]], addresses)

        _logger.debug(
            "No Addresses found for Service %s in Namespace %s, sleeping for 1 minute (attempt: %s)",
            name,
            namespace,
            attempt,
        )
    else:
        return []


def get_ingress_dns(name: str, k8s_context: str, namespace: str = "default") -> str:
    config.load_kube_config(context=k8s_context)

    network = NetworkingV1beta1Api()
    for attempt in range(15):
        time.sleep(60)
        try:
            resp: NetworkingV1beta1IngressList = network.list_namespaced_ingress(namespace=namespace)
            _logger.debug(resp)
            for i in resp.items:
                item: Dict[str, Any] = i.to_dict()
                if item["metadata"]["name"] == name:
                    if "load_balancer" in item["status"]:
                        if "ingress" in item["status"]["load_balancer"]:
                            if item["status"]["load_balancer"]["ingress"]:
                                if "hostname" in item["status"]["load_balancer"]["ingress"][0]:
                                    return str(item["status"]["load_balancer"]["ingress"][0]["hostname"])
                                else:
                                    _logger.debug("hostname is not defined ")
                            else:
                                _logger.debug("ingress[] is empty")
                        else:
                            _logger.debug("ingress not in load_balancer")
                    else:
                        _logger.debug("no load_balancer in status")
            else:
                _logger.debug(f"Cannot find Ingress {name}.{namespace}")
        except Exception:
            _logger.exception(f"Error finding Ingress {name}.{namespace}")

        _logger.info("Waiting for for Ingress %s.%s, sleeping for 1 minute (attempt: %s)", name, namespace, attempt)
    else:
        raise Exception(f"Timeout while waiting for Ingress {name}.{namespace}")


def get_resource_status(name: str, k8s_context: str, type: str, namespace: str = "orbit-system") -> Dict[str, Any]:
    _logger.debug("Retrieving Status for %s %s in Namespace %s", type, name, namespace)
    config.load_kube_config(context=k8s_context)
    apps = AppsV1Api()
    if type.lower() == "statefulset":
        api = apps.read_namespaced_stateful_set_status
    elif type.lower() == "deployment":
        api = apps.read_namespaced_deployment_status
    else:
        raise Exception("Unknown resource type")

    resp = api(name=name, namespace=namespace)
    resource = resp.to_dict()
    return cast(Dict[str, Any], resource.get("status"))


if __name__ == "__main__":
    k8s_context = config.load_kube_config()
    r = get_ingress_dns(name="istio-ingress", k8s_context=k8s_context, namespace="istio-system")
    _logger.debug(r)
