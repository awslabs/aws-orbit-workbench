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

from typing import cast

import aws_cdk.core as core
from aws_cdk import aws_lambda

from aws_orbit.manifest import Manifest
from aws_orbit.manifest.team import TeamManifest
from aws_orbit.remote_files.cdk import _lambda_path


class LambdaBuilder:
    @staticmethod
    def get_or_build_construct_request(
        scope: core.Construct,
        manifest: Manifest,
        team_manifest: TeamManifest,
    ) -> aws_lambda.Function:
        stack = core.Stack.of(cast(core.IConstruct, scope))
        lambda_function = cast(aws_lambda.Function, stack.node.try_find_child("construct_request"))
        if lambda_function is None:
            lambda_function = aws_lambda.Function(
                scope=stack,
                id="construct_request",
                function_name=f"orbit-{manifest.name}-{team_manifest.name}-k8s-construct-request",
                code=aws_lambda.Code.asset(_lambda_path("construct_request")),
                handler="index.handler",
                runtime=aws_lambda.Runtime.PYTHON_3_6,
                timeout=core.Duration.seconds(10),
            )
        return lambda_function
