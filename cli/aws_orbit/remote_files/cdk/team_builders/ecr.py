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


from typing import TYPE_CHECKING, Optional

import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_ecs as ecs
import aws_cdk.core as core

from aws_orbit.models.context import construct_ecr_repository_name

if TYPE_CHECKING:
    from aws_orbit.models.context import Context


class EcrBuilder:
    @staticmethod
    def build_ecr_image(scope: core.Construct, context: "Context", image: Optional[str]) -> ecs.EcrImage:
        repository_name, tag = construct_ecr_repository_name(env_name=context.name, image=image).split(":")
        repository = ecr.Repository.from_repository_name(
            scope,
            "ecr_repository",
            repository_name=repository_name,
        )
        return ecs.ContainerImage.from_ecr_repository(repository=repository, tag=tag)
