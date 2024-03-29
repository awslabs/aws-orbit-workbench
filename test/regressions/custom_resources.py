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
from typing import Any, Dict, List, cast, Optional, Union

import yaml
from kubernetes import dynamic
from kubernetes.client import V1DeleteOptions, V1Status, api_client
from kubetest.manifest import render
from kubetest.objects import ApiObject
from kubetest.client import TestClient
from kubernetes.client.rest import ApiException
from kubetest import condition, utils
from common_utils import *
from kubernetes import config as k8_config

# This elminates some collection warnings for all tests using the TestClient
TestClient.__test__ = False

log = logging.getLogger("kubetest")


class CustomApiObject(ApiObject):  # type: ignore
    group: str = ""
    api_version: str = ""
    kind: str = ""

    obj: Dict[str, Any] = {}
    obj_type = dynamic.Resource
    api_clients = {"preferred": dynamic.DynamicClient}

    def __init__(self, resource: Dict[str, Any]) -> None:
        self.obj = resource

        self._api_client = None

    @property
    def version(self) -> str:
        return cast(str, self.obj["apiVersion"])

    @property
    def name(self) -> str:
        return cast(str, self.obj["metadata"].get("name"))

    @name.setter
    def name(self, name: str) -> None:
        self.obj["metadata"]["name"] = name

    @property
    def namespace(self) -> Optional[str]:
        return cast(Optional[str], self.obj["metadata"].get("namespace"))

    @namespace.setter
    def namespace(self, name: str) -> None:
        """Set the namespace of the object, if it hasn't already been set.

        Raises:
            AttributeError: The namespace has already been set.
        """
        if self.obj["metadata"].get("namespace") is None:
            self.obj["metadata"]["namespace"] = name
        else:
            raise AttributeError("Cannot set namespace - object already has a namespace")

    def refresh_api_client(self) -> None:
        c = self.api_clients.get(self.version)
        # If we didn't find the client in the api_clients dict, use the
        # preferred version.
        if c is None:
            c = self.api_clients.get("preferred")
            if c is None:
                raise ValueError(
                    "unknown version specified and no preferred version " f"defined for resource ({self.version})"
                )
        # If we did find it, initialize that client version.
        self._api_client = c(client=api_client.ApiClient()).resources.get(
            group=self.group, api_version=self.api_version, kind=self.kind
        )

    @property
    def api_client(self) -> dynamic.DynamicClient:
        self.refresh_api_client()
        k8_config.load_kube_config()
        return self._api_client

    @classmethod
    def preferred_client(cls) -> dynamic.DynamicClient:
        c = cls.api_clients.get("preferred")
        if c is None:
            raise ValueError(
                f"no preferred api client defined for object {cls.__name__}",
            )
        return c(client=api_client.ApiClient()).resources.get(
            group=cls.group, api_version=cls.api_version, kind=cls.kind
        )

    @classmethod
    def _load(cls, path: str, name: Optional[str] = None) -> List[ApiObject]:
        with open(path, "r") as f:
            content = render(f, dict(path=path))
            objs = yaml.load_all(content, Loader=yaml.SafeLoader)
            filtered = [
                o
                for o in objs
                if o and o.get("apiVersion") == f"{cls.group}/{cls.api_version}" and o.get("kind") == cls.kind
            ]

        if len(filtered) == 0:
            raise ValueError(
                "Unable to load resource from file - no resource definitions found "
                f"with type {cls.group}/{cls.api_version}/{cls.kind}."
            )
        else:
            return filtered

    @classmethod
    def load(cls, path: str, name: Optional[str] = None) -> ApiObject:
        filtered = cls._load(path=path, name=name)
        if len(filtered) == 1:
            return cls(filtered[0])

        # If we get here, there are multiple objects of the same type defined. We
        # need to check that a name is provided and return the object whose name
        # matches.
        if not name:
            raise ValueError(
                "Unable to load resource from file - multiple resource definitions "
                f"found for {cls.group}/{cls.api_version}/{cls.kind}, but no name "
                "specified to select which one."
            )

        for o in filtered:
            if o.get("metadata", {}).get("name") == name:
                return cls(o)
        else:
            raise ValueError(
                "Unable to load resource from file - multiple resource definitions found for "
                f"{cls.group}/{cls.api_version}/{cls.kind}, but none match specified name: {name}"
            )

    @classmethod
    def load_all(cls, path: str) -> List[ApiObject]:
        filtered = cls._load(path=path)
        return [cls(o) for o in filtered]

    def create(self, namespace: Optional[str] = None) -> None:
        if namespace is None:
            namespace = self.namespace

        log.info(f'creating resource "{self.name}" in namespace "{self.namespace}"')
        log.debug(f"resource: {self.obj}")

        self.obj = self.api_client.create(
            namespace=namespace,
            body=self.obj,
        ).to_dict()

    def delete(self, options: V1DeleteOptions = None) -> V1Status:
        if options is None:
            options = V1DeleteOptions()

        log.info(f'deleting resource "{self.name}"')
        log.debug(f"delete options: {options}")
        log.debug(f"resource: {self.obj}")

        return self.api_client.delete(
            name=self.name,
            namespace=self.namespace,
            body=options,
        )

    def refresh(self) -> None:
        self.obj = self.api_client.get(
            name=self.name,
            namespace=self.namespace,
        ).to_dict()


class OrbitJobCustomApiObject(CustomApiObject):
    group = "orbit.aws"
    api_version = "v1"
    kind = "OrbitJob"

    def __init__(self, resource: Dict[str, Any]) -> None:
        self.obj = resource
        self._api_client = None

    def get_status(self) -> Dict[str,Any]:
        self.refresh()
        status_dict = self.obj.get("status", {})
        return status_dict

    # We are ready as soon as we see some status
    def is_ready(self) -> bool:
        self.refresh()
        log.info(self.obj.get("status", {}).get("orbitJobOperator", {}))
        return_status = False
        if self.obj.get("status", {}).get("orbitJobOperator", {}).get("jobStatus"):
            return_status = True
        return return_status

    # We are complete as soon as we see status as complete or Failed
    def is_complete(self) -> bool:
        self.refresh()
        log.info(self.obj.get("status", {}).get("orbitJobOperator", {}))
        return self.obj.get("status", {}).get("orbitJobOperator", {}).get("jobStatus") in [
            JOB_COMPLETION_STATUS,
            JOB_FAILED_STATUS
        ]

    def wait_until_job_completes(
        self,
        timeout: int = None,
        interval: Union[int, float] = 5,
        fail_on_api_error: bool = False,
    ) -> None:
        """Wait until the orbit job completes. Can have completed or failed state

        Args:
            timeout: The maximum time to wait, in seconds, for the resource
                to reach the ready state. If unspecified, this will wait
                indefinitely. If specified and the timeout is met or exceeded,
                a TimeoutError will be raised.
            interval: The time, in seconds, to wait before re-checking if the
                object is ready.
            fail_on_api_error: Fail if an API error is raised. An API error can
                be raised for a number of reasons, such as 'resource not found',
                which could be the case when a resource is just being started or
                restarted. When waiting for readiness we generally do not want to
                fail on these conditions.

        Raises:
             TimeoutError: The specified timeout was exceeded.
        """
        job_complete_condition = condition.Condition(
            "orbit job status check",
            self.is_complete,
        )
        # Wait until Orbit job completes
        utils.wait_for_condition(
            condition=job_complete_condition,
            timeout=timeout,
            interval=interval,
            fail_on_api_error=fail_on_api_error,
        )


class OrbitUserSpaceCrObject(CustomApiObject):
    group = "orbit.aws"
    api_version = "v1"
    kind = "UserSpace"

    def __init__(self, resource: Dict[str, Any]) -> None:
        self.obj = resource
        self._api_client = None

    def get_status(self) -> Dict[str,Any]:
        self.refresh()
        status_dict = self.obj.get("status", {})
        return status_dict

    def check_userspace_exists(self) -> bool:
        cr_status = False
        try:
            self.api_client.get
            api_response = self.api_client.get(name=self.name,namespace=self.namespace)
            log.info(api_response)
            cr_status = True
        except ApiException as e:
            log.info(f"{e.body}")
        return cr_status

    # We are ready as soon as we see some status
    def is_ready(self) -> bool:
        self.refresh()
        log.info(self.obj.get("status", {}).get("userSpaceOperator", {}))
        return_status = False
        if self.obj.get("status", {}).get("userSpaceOperator", {}).get("installationStatus"):
            return_status = True
        return return_status

    # We are complete as soon as we see status as complete or Failed
    def is_complete(self) -> bool:
        self.refresh()
        log.info(self.obj.get("status", {}).get("userSpaceOperator", {}))
        return self.obj.get("status", {}).get("userSpaceOperator", {}).get("installationStatus") in [
            USERSPACE_INSTALLED_STATUS,
            USERSPACE_FAILED_STATUS
        ]

    def wait_until_userspace_installation(
        self,
        timeout: int = None,
        interval: Union[int, float] = 5,
        fail_on_api_error: bool = False,
    ) -> None:
        userspace_condition = condition.Condition(
            "orbit userspace status check",
            self.is_complete,
        )
        # Wait until UserSpace based Helm charts install
        utils.wait_for_condition(
            condition=userspace_condition,
            timeout=timeout,
            interval=interval,
            fail_on_api_error=fail_on_api_error,
        )