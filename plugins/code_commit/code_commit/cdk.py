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
from typing import TYPE_CHECKING, Any, Dict, cast

import aws_cdk.aws_codecommit as codecommit
import aws_cdk.aws_iam as iam
from aws_cdk.core import Construct, Environment, IConstruct, Stack, Tags
from aws_orbit.plugins.helpers import cdk_handler

if TYPE_CHECKING:
    from aws_orbit.models.context import Context, TeamContext

_logger: logging.Logger = logging.getLogger(__name__)


class Team(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        context: "Context",
        team_context: "TeamContext",
        parameters: Dict[str, Any],
    ) -> None:

        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=context.account_id, region=context.region),
        )
        Tags.of(scope=cast(IConstruct, self)).add(key="Env", value=f"orbit-{context.name}")

        repo: codecommit.Repository = codecommit.Repository(
            scope=self,
            id="repo",
            repository_name=f"orbit-{context.name}-{team_context.name}",
        )

        if team_context.eks_pod_role_arn is None:
            raise ValueError("Pod Role arn required")
        team_role = iam.Role.from_role_arn(
            scope=self,
            id="team-role",
            role_arn=team_context.eks_pod_role_arn,
            mutable=True,
        )
        team_role.attach_inline_policy(
            policy=iam.Policy(
                scope=self,
                id="codecommit",
                policy_name="codecommit",
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "codecommit:CreateBranch",
                            "codecommit:DeleteCommentContent",
                            "codecommit:ListPullRequests",
                            "codecommit:UpdatePullRequestApprovalRuleContent",
                            "codecommit:PutFile",
                            "codecommit:GetPullRequestApprovalStates",
                            "codecommit:CreateCommit",
                            "codecommit:ListTagsForResource",
                            "codecommit:BatchDescribeMergeConflicts",
                            "codecommit:GetCommentsForComparedCommit",
                            "codecommit:DeletePullRequestApprovalRule",
                            "codecommit:GetCommentReactions",
                            "codecommit:GetComment",
                            "codecommit:UpdateComment",
                            "codecommit:MergePullRequestByThreeWay",
                            "codecommit:CreatePullRequest",
                            "codecommit:UpdatePullRequestApprovalState",
                            "codecommit:GetPullRequestOverrideState",
                            "codecommit:PostCommentForPullRequest",
                            "codecommit:GetRepositoryTriggers",
                            "codecommit:UpdatePullRequestDescription",
                            "codecommit:GetObjectIdentifier",
                            "codecommit:BatchGetPullRequests",
                            "codecommit:GetFile",
                            "codecommit:GetUploadArchiveStatus",
                            "codecommit:MergePullRequestBySquash",
                            "codecommit:GetDifferences",
                            "codecommit:GetRepository",
                            "codecommit:GetMergeConflicts",
                            "codecommit:GetMergeCommit",
                            "codecommit:PostCommentForComparedCommit",
                            "codecommit:GitPush",
                            "codecommit:GetMergeOptions",
                            "codecommit:AssociateApprovalRuleTemplateWithRepository",
                            "codecommit:PutCommentReaction",
                            "codecommit:GetTree",
                            "codecommit:BatchAssociateApprovalRuleTemplateWithRepositories",
                            "codecommit:GetReferences",
                            "codecommit:GetBlob",
                            "codecommit:DescribeMergeConflicts",
                            "codecommit:UpdatePullRequestTitle",
                            "codecommit:GetCommit",
                            "codecommit:OverridePullRequestApprovalRules",
                            "codecommit:GetCommitHistory",
                            "codecommit:GetCommitsFromMergeBase",
                            "codecommit:BatchGetCommits",
                            "codecommit:TestRepositoryTriggers",
                            "codecommit:DescribePullRequestEvents",
                            "codecommit:UpdatePullRequestStatus",
                            "codecommit:CreatePullRequestApprovalRule",
                            "codecommit:UpdateDefaultBranch",
                            "codecommit:GetPullRequest",
                            "codecommit:PutRepositoryTriggers",
                            "codecommit:UploadArchive",
                            "codecommit:ListAssociatedApprovalRuleTemplatesForRepository",
                            "codecommit:MergeBranchesBySquash",
                            "codecommit:ListBranches",
                            "codecommit:GitPull",
                            "codecommit:BatchGetRepositories",
                            "codecommit:GetCommentsForPullRequest",
                            "codecommit:BatchDisassociateApprovalRuleTemplateFromRepositories",
                            "codecommit:CancelUploadArchive",
                            "codecommit:GetFolder",
                            "codecommit:PostCommentReply",
                            "codecommit:MergeBranchesByFastForward",
                            "codecommit:CreateUnreferencedMergeCommit",
                            "codecommit:EvaluatePullRequestApprovalRules",
                            "codecommit:MergeBranchesByThreeWay",
                            "codecommit:GetBranch",
                            "codecommit:DisassociateApprovalRuleTemplateFromRepository",
                            "codecommit:MergePullRequestByFastForward",
                            "codecommit:DeleteFile",
                            "codecommit:DeleteBranch",
                        ],
                        resources=[repo.repository_arn],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "codecommit:ListRepositoriesForApprovalRuleTemplate",
                            "codecommit:CreateApprovalRuleTemplate",
                            "codecommit:UpdateApprovalRuleTemplateName",
                            "codecommit:GetApprovalRuleTemplate",
                            "codecommit:ListApprovalRuleTemplates",
                            "codecommit:DeleteApprovalRuleTemplate",
                            "codecommit:ListRepositories",
                            "codecommit:UpdateApprovalRuleTemplateContent",
                            "codecommit:UpdateApprovalRuleTemplateDescription",
                        ],
                        resources=["*"],
                    ),
                ],
            )
        )


if __name__ == "__main__":
    cdk_handler(stack_class=Team)
