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
    name="datamaker-cli",
    version="0.0a0",
    packages=find_packages(include=["datamaker_cli", "datamaker_cli.*"]),
    python_requires=">=3.6, <3.9",
    install_requires=open("requirements.txt").read().strip().split("\n"),
    entry_points={"console_scripts": ["datamaker = datamaker_cli.__main__:main"]},
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    package_data={"datamaker_cli": ["kubectl/models/*.yaml"]},
    include_package_data=True,
)
