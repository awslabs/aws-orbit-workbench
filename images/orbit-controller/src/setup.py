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

from setuptools import find_packages, setup

setup(
    name="orbit-controller",
    version="0.1.0",
    author="AWS Professional Services",
    author_email="aws-proserve-opensource@amazon.com",
    url="https://github.com/awslabs/aws-orbit-workbench",
    project_urls={"Org Site": "https://aws.amazon.com/professional-services/"},
    packages=find_packages(include=["orbit_controller", "orbit_controller.*"]),
    python_requires=">=3.7, <3.9",
    install_requires=[
        "boto3~=1.19.0",
        "click~=7.1.0",
        "kubernetes~=12.0.1",
        "pyyaml~=5.4",
        "requests>=2.25.1,<2.32.0",
        "jsonpatch~=1.32",
        "flask>=1.1.2,<2.3.0",
        "gunicorn~=20.1.0",
        "jsonpath-ng~=1.5.0",
        "cryptography>=3.4.7,<39.1.0",
        "python-jose~=3.2.0",
        "kopf~=1.33.0",
    ],
    include_package_data=True,
)
