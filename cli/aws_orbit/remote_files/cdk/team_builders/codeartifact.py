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

from typing import Any

from aws_cdk import aws_codeartifact as codeartifact
from aws_cdk import core


class DeployCodeArtifact(core.Construct):
    def __init__(
        self,
        scope: core.Construct,
        id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, id)

        self.artifact_domain = codeartifact.CfnDomain(self, id="Orbit CodeArtifact Domain", domain_name="aws-orbit")
        self.pypi_repo = codeartifact.CfnRepository(
            self,
            id="Orbit CodeArtifact Python Repo",
            domain_name=self.artifact_domain.domain_name,
            repository_name="python-repository",
            external_connections=["public:pypi"],
            description="Provides PyPI artifacts for AWS Orbit.",
        )
        self.pypi_repo.add_depends_on(self.artifact_domain)
