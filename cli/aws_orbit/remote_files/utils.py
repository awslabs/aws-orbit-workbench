import logging
from typing import TYPE_CHECKING, List

from kubernetes import config

_logger: logging.Logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from aws_orbit.manifest import Manifest


def get_k8s_context(manifest: "Manifest") -> str:
    try:
        contexts: List[str] = [str(c["name"]) for c in config.list_kube_config_contexts()[0]]
    except config.config_exception.ConfigException as e:
        _logger.debug("Context not found")
        raise e
    expected_domain: str = f"@orbit-{manifest.name}.{manifest.region}.eksctl.io"
    for context in contexts:
        if context.endswith(expected_domain):
            return context
    raise RuntimeError(f"Context not found for domain: {expected_domain}")
