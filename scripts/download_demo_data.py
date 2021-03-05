import sys
import logging

from aws_orbit.remote_files.demo import _prepare_demo_data
from aws_orbit.models.context import Context
from aws_orbit.models.context import load_context_from_ssm

_logger: logging.Logger = logging.getLogger(__name__)

# Helper function to download the demo data from public sites.
# Usage - python download_demo_data.py dev_env

def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 2:
        env_name = sys.argv[1]
    else:
        raise ValueError("Orbit environment name required")
        sys.exit(1)
    try:
        _logger.info(f"Preparing context for environment {env_name}")
        context: "Context" = load_context_from_ssm(env_name=env_name)
        _prepare_demo_data(context=context)
    except Exception as ex:
        error = ex.response["Error"]
        _logger.error("Invalid environment %s. Cause: %s", env_name, error)
        sys.exit(1)


if __name__ == "__main__":
    main()
