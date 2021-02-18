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

from setuptools import setup

setup(
    name="orbit-codecommit",
    version="0.0b0",
    description="Orbit Workbench CodeCommit Plugin.",
    license="Apache License 2.0",
    packages=["code_commit"],
    python_requires=">=3.6, <3.9",
    install_requires=[
        "aws-cdk.aws-codecommit~=1.67.0",
        "aws-cdk.aws-iam~=1.67.0",
    ],
    include_package_data=True,
)
