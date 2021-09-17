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
import yaml

from typing import Dict, List, Optional, Union

from kubernetes.client import api_client, V1DeleteOptions, V1Status
from kubernetes.client.rest import ApiException
from kubernetes import dynamic
from kubetest.manifest import render
from kubetest.objects import ApiObject

log = logging.getLogger("kubetest")


class CustomApiObject(ApiObject):
    group = None
    api_version = None
    kind = None

    obj_type = dynamic.Resource
    api_clients = {
        "preferred": dynamic.DynamicClient
    }

    def __init__(self, resource) -> None:
        self.obj = resource

        self._api_client = None

    @property
    def version(self) -> str:
        return self.obj["apiVersion"]

    @property
    def name(self) -> str:
        return self.obj["metadata"].get("name")

    @name.setter
    def name(self, name: str):
        self.obj["metadata"]["name"] = name

    @property
    def namespace(self) -> str:
        return self.obj["metadata"].get("namespace")

    @namespace.setter
    def namespace(self, name: str):
        """Set the namespace of the object, if it hasn't already been set.

        Raises:
            AttributeError: The namespace has already been set.
        """
        if self.obj["metadata"].get("namespace") is None:
            self.obj["metadata"]["namespace"] = name
        else:
            raise AttributeError(
                "Cannot set namespace - object already has a namespace"
            )

    @property
    def api_client(self):
        if self._api_client is None:
            c = self.api_clients.get(self.version)
            # If we didn't find the client in the api_clients dict, use the
            # preferred version.
            if c is None:
                log.warning(
                    f"unknown version ({self.version}), falling back to preferred version"
                )
                c = self.api_clients.get("preferred")
                if c is None:
                    raise ValueError(
                        "unknown version specified and no preferred version "
                        f"defined for resource ({self.version})"
                    )
            # If we did find it, initialize that client version.
            self._api_client = c(client=api_client.ApiClient()).resources.get(group=self.group, api_version=self.api_version, kind=self.kind)
        return self._api_client

    @classmethod
    def preferred_client(cls):
        c = cls.api_clients.get("preferred")
        if c is None:
            raise ValueError(
                f"no preferred api client defined for object {cls.__name__}",
            )
        return c(client=api_client.ApiClient()).resources.get(group=cls.group, api_version=cls.api_version, kind=cls.kind)

    @classmethod
    def _load(cls, path: str, name: Optional[str] = None) -> List[ApiObject]:
        with open(path, "r") as f:
            content = render(f, dict(path=path))
            objs = yaml.load_all(content, Loader=yaml.SafeLoader)
            filtered = [o for o in objs if o and o.get("apiVersion") == f"{cls.group}/{cls.api_version}" and o.get("kind") == cls.kind]

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
    def load_all(cls, path: str) -> ApiObject:
        filtered = cls._load(path=path)
        return [cls(o) for o in filtered]

    def create(self, namespace: str = None) -> None:
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
