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

import time
import logging
from typing import Union
from kubernetes.client.rest import ApiException
from kubernetes import config as k8_config
from kubetest import condition

JOB_COMPLETION_STATUS = "Complete"
JOB_FAILED_STATUS = "Failed"

log = logging.getLogger("kubetest")


def wait_for_custom_condition(
    condition: condition.Condition,
    timeout: int = None,
    interval: Union[int, float] = 1,
    fail_on_api_error: bool = True,
) -> None:
    """Wait for a condition to be met.

    Args:
        condition: The Condition to wait for.
        timeout: The maximum time to wait, in seconds, for the condition to be met.
            If unspecified, this function will wait indefinitely. If specified and
            the timeout is met or exceeded, a TimeoutError will be raised.
        interval: The time, in seconds, to wait before re-checking the condition.
        fail_on_api_error: Fail the condition checks if a Kubernetes API error is
            incurred. An API error can be raised for a number of reasons, including
            a Pod being restarted and temporarily unavailable. Disabling this will
            cause those errors to be ignored, allowing the check to continue until
            timeout or resolution. (default: True).

    Raises:
        TimeoutError: The specified timeout was exceeded.
    """
    log.info(f"waiting for condition: {condition}")

    # define the maximum time to wait. once this is met, we should
    # stop waiting.
    max_time = None
    if timeout is not None:
        max_time = time.time() + timeout

    # start the wait block
    start = time.time()
    count = 0
    retry_count = 3
    while True:
        if max_time and time.time() >= max_time:
            raise TimeoutError(
                f"timed out ({timeout}s) while waiting for condition {condition}"
            )

        # check if the condition is met and break out if it is
        try:
            if condition.check():
                break
        except ApiException as e:
            log.info(type(e))
            log.warning(f"got api exception while waiting: {e}")
            if count < retry_count:
                if e.reason == 'Unauthorized':
                    k8_config.load_kube_config()
                    log.info("loading the kubeconfig during Unauthorized exception and retrying")
                    count+=1
                    continue
                else:
                    raise
            else:
                log.info(f"retried loading kubeconfig {retry_count} times")
                raise

        # if the condition is not met, sleep for the interval
        # to re-check later
        time.sleep(interval)

    end = time.time()
    log.info(f"wait completed (total={end-start}s) {condition}")
