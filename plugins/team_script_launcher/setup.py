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
    name="team_script_launcher",
    version="0.0b0",
    description="Launch a Pod for the team space that executes a script given by the user",
    license="Apache License 2.0",
    packages=["team_script_launcher"],
    python_requires=">=3.6, <3.9",
    install_requires=open("requirements.txt").read().strip().split("\n"),
    include_package_data=True,
    package_data={"team_script_launcher": ["*.yaml"]},
)
