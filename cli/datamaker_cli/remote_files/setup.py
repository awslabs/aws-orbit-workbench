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

import os
from io import open
from typing import Dict

from setuptools import find_packages, setup

cdk_version = "~=1.67.0"
cdk_modules = [
    "aws_cdk.core",
    "aws-cdk.aws-ec2",
    "aws-cdk.aws-iam",
    "aws-cdk.aws-efs",
    "aws-cdk.aws-ecr",
    "aws-cdk.aws-ecs",
    "aws-cdk.aws-ssm",
    "aws_cdk.aws_cognito",
]

here = os.path.abspath(os.path.dirname(__file__))
about: Dict[str, str] = {}
path = os.path.join(here, "datamaker_cli", "__metadata__.py")
with open(file=path, mode="r", encoding="utf-8") as f:
    exec(f.read(), about)

setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    license=about["__license__"],
    packages=find_packages(include=["datamaker_cli", "datamaker_cli.*"]),
    python_requires=">=3.6, <3.9",
    install_requires=[
        "boto3~=1.12",
        "botocore~=1.15",
        "PyYAML~=5.3.0",
        "click~=7.1.0",
        "kubernetes~=11.0.0",
        "sh~=1.14.0",
    ]
    + [f"{m}{cdk_version}" for m in cdk_modules],
    entry_points={"console_scripts": ["datamaker = datamaker_cli.__main__:main"]},
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    package_data={"datamaker_cli": ["data/k8s/*.yaml", "data/toolkit/*.yaml"]},
    include_package_data=True,
)
