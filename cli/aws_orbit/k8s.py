import json
import logging
import time

from datetime import date, datetime
from typing import Any, Dict, cast

from kubernetes import config
from kubernetes.client import CoreV1Api, V1Service

_logger: logging.Logger = logging.getLogger(__name__)


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))


def get_service_hostname(name: str, k8s_context: str, namespace: str = "default") -> str:
    config.load_kube_config(context=k8s_context)
    v1 = CoreV1Api()
    while True:
        resp = cast(V1Service, v1.read_namespaced_service_status(name=name, namespace=namespace))
        _logger.debug("K8s Response:\n", json.dumps(resp, default=json_serial))
        status: Dict[str, Any] = resp.status.to_dict()
        if "load_balancer" in status:
            if "ingress" in status["load_balancer"]:
                if status["load_balancer"]["ingress"]:
                    if "hostname" in status["load_balancer"]["ingress"][0]:
                        break
        time.sleep(10)
    return str(status["load_balancer"]["ingress"][0]["hostname"])
