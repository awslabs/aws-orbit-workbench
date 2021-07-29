import logging
from typing import TYPE_CHECKING, List

from kubernetes import config

_logger: logging.Logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from aws_orbit.models.context import Context


def get_k8s_context(context: "Context") -> str:
    try:
        contexts: List[str] = [str(c["name"]) for c in config.list_kube_config_contexts()[0]]
    except config.config_exception.ConfigException as e:
        _logger.exception("Context not found")
        raise e
    expected_domain: str = f"@orbit-{context.name}.{context.region}.eksctl.io"
    for ctx in contexts:
        if ctx.endswith(expected_domain):
            return ctx
    raise RuntimeError(f"Context not found for domain: {expected_domain}")
