import logging
import time
from typing import Any, Dict, List, cast

from kubernetes import config
from kubernetes.client import CoreV1Api, NetworkingV1beta1Api, NetworkingV1beta1IngressList, V1Service

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


def get_service_endpoints(name: str, k8s_context: str, namespace: str = "orbit-system") -> List[Dict[str, Any]]:
    _logger.debug("Retrieving Endpoints for Service %s in Namespace %s", name, namespace)
    config.load_kube_config(context=k8s_context)
    v1 = CoreV1Api()
    for _ in range(10):
        resp = v1.read_namespaced_endpoints(name=name, namespace=namespace)
        endpoints = resp.to_dict()
        subsets = endpoints.get("subsets")
        if subsets and len(subsets) > 0:
            return cast(List[Dict[str, Any]], endpoints["subsets"])
        else:
            _logger.debug("No Endpoints found for Service %s in Namespace %s, sleeping for 1 minute", name, namespace)
            time.sleep(60)
    else:
        return []


def get_ingress_dns(name: str, k8s_context: str, namespace: str = "default") -> str:
    config.load_kube_config(context=k8s_context)

    network = NetworkingV1beta1Api()
    timeout = 30 * 60
    wait = 30
    while True:
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
                raise Exception(f"Cannot find Ingress {name}.{namespace}")
        except Exception:
            _logger.debug(f"Cannot find Ingress {name}.{namespace}")

        time.sleep(wait)
        timeout = timeout - wait
        _logger.info(f"Waiting for for Ingress {name}.{namespace}")
        if timeout < 0:
            raise Exception(f"Timeout while waiting for Ingress {name}.{namespace}")


if __name__ == "__main__":
    k8s_context = config.load_kube_config()
    r = get_ingress_dns(name="istio-ingress", k8s_context=k8s_context, namespace="istio-system")
    _logger.debug(r)
