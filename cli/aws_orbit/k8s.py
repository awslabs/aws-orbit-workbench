import logging
import time
from typing import Any, Dict, cast

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


def get_ingress_dns(name: str, k8s_context: str, namespace: str = "default") -> str:
    config.load_kube_config(context=k8s_context)

    network = NetworkingV1beta1Api()
    timeout = 15 * 60
    wait = 30
    while True:
        try:
            resp: NetworkingV1beta1IngressList = network.list_namespaced_ingress(namespace=namespace)
            print(resp)
            for i in resp.items:
                item: Dict[str, Any] = i.to_dict()
                if item["metadata"]["name"] == name:
                    if "load_balancer" in item["status"]:
                        if "ingress" in item["status"]["load_balancer"]:
                            if item["status"]["load_balancer"]["ingress"]:
                                if "hostname" in item["status"]["load_balancer"]["ingress"][0]:
                                    return str(item["status"]["load_balancer"]["ingress"][0]["hostname"])
                                else:
                                    print("hostname is not defined ")
                            else:
                                print("ingress[] is empty")
                        else:
                            print("ingress not in load_balancer")
                    else:
                        print("no load_balancer in status")
            else:
                raise Exception(f"Cannot find Ingress {name}.{namespace}")
        except Exception:
            print(f"Cannot find Ingress {name}.{namespace}")

        time.sleep(wait)
        timeout = timeout - wait
        _logger.info(f"Waiting for for Ingress {name}.{namespace}")
        if timeout < 0:
            raise Exception(f"Timeout while waiting for Ingress {name}.{namespace}")


if __name__ == "__main__":
    k8s_context = config.load_kube_config()
    r = get_ingress_dns(name="istio-ingress", k8s_context=k8s_context, namespace="istio-system")
    print(r)
