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
import os
import shutil
import sys

import aws_cdk.aws_codecommit as codecommit
import aws_cdk.aws_iam as iam
from aws_cdk.core import App, Construct, Environment, Stack, Tags
from datamaker_cli.manifest import Manifest
from datamaker_cli.manifest.team import TeamManifest

_logger: logging.Logger = logging.getLogger(__name__)


class Team(Stack):
    def __init__(self, scope: Construct, id: str, manifest: Manifest, team_manifest: TeamManifest) -> None:
        self.scope = scope
        self.id = id
        self.manifest = manifest
        self.team_manifest = team_manifest
        super().__init__(
            scope=scope,
            id=id,
            stack_name=id,
            env=Environment(account=self.manifest.account_id, region=self.manifest.region),
        )
        Tags.of(scope=self).add(key="Env", value=f"datamaker-{self.manifest.name}")

        repo: codecommit.Repository = codecommit.Repository(
            scope=self,
            id="repo",
            repository_name=f"datamaker-{self.manifest.name}-{self.team_manifest.name}",
        )

        team_role: iam.Role = iam.Role.from_role_arn(
            scope=self, id="team-role", role_arn=team_manifest.eks_nodegroup_role_arn, mutable=True
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


def main() -> None:
    _logger.debug("sys.argv: %s", sys.argv)
    if len(sys.argv) == 3:
        filename: str = sys.argv[1]
        team_name: str = sys.argv[2]
    else:
        raise ValueError("Unexpected number of values in sys.argv.")

    manifest: Manifest = Manifest(filename=filename)
    manifest.fillup()

    for team in manifest.teams:
        if team.name == team_name:
            team_manifest: TeamManifest = team
            break
    else:
        raise ValueError(f"Team {team_name} not found in the manifest.")

    stack_name = f"datamaker-{manifest.name}-{team_manifest.name}-codecommit"
    outdir = os.path.join(
        manifest.filename_dir,
        ".datamaker.out",
        manifest.name,
        "cdk",
        stack_name,
    )
    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)

    app = App(outdir=outdir)
    Team(scope=app, id=stack_name, manifest=manifest, team_manifest=team_manifest)
    app.synth(force=True)


if __name__ == "__main__":
    main()
