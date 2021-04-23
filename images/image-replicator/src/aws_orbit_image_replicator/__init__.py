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

import logging
import multiprocessing
import sys

from kubernetes import config as k8_config

formatter = logging.Formatter("[%(asctime)s][%(filename)-13s:%(lineno)3d] %(levelname)-8s %(message)s")
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

logger = multiprocessing.get_logger()
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)


def load_config(in_cluster: bool) -> None:
    if in_cluster:
        k8_config.load_incluster_config()
    else:
        k8_config.load_kube_config()
