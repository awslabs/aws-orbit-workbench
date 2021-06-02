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

from notebook.utils import url_path_join

from .handlers.athena import AthenaRouteHandler
from .handlers.catalog import CatalogRouteHandler
from .handlers.containers import ContainersRouteHandler
from .handlers.eks import EksRouteHandler
from .handlers.redshift import RedshiftRouteHandler
from .handlers.storage import StorageRouteHandler
from .handlers.team import TeamRouteHandler


def setup_handlers(web_app):
    base_url: str = web_app.settings["base_url"]
    handlers = [
        (url_path_join(base_url, "jupyterlab_orbit", "catalog"), CatalogRouteHandler),
        (
            url_path_join(base_url, "jupyterlab_orbit", "containers"),
            ContainersRouteHandler,
        ),
        (url_path_join(base_url, "jupyterlab_orbit", "team"), TeamRouteHandler),
        (url_path_join(base_url, "jupyterlab_orbit", "redshift"), RedshiftRouteHandler),
        (url_path_join(base_url, "jupyterlab_orbit", "athena"), AthenaRouteHandler),
        (url_path_join(base_url, "jupyterlab_orbit", "storage"), StorageRouteHandler),
        (url_path_join(base_url, "jupyterlab_orbit", "eks"), EksRouteHandler),
    ]

    host_pattern: str = ".*$"
    web_app.add_handlers(host_pattern, handlers)
