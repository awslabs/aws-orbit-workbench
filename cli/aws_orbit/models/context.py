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

# flake8: noqa: F811

import concurrent.futures
import json
import logging
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Generic, List, Optional, Type, TypeVar, Union, cast

import botocore.exceptions
from dataclasses import field
from marshmallow import Schema
from marshmallow_dataclass import dataclass

import aws_orbit
from aws_orbit import utils
from aws_orbit.models.common import BaseSchema
from aws_orbit.models.manifest import (
    DataNetworkingManifest,
    FoundationImagesManifest,
    FoundationManifest,
    FrontendNetworkingManifest,
    ImagesManifest,
    ManagedNodeGroupManifest,
    Manifest,
    NetworkingManifest,
    PluginManifest,
    TeamManifest,
)
from aws_orbit.services import ssm
from aws_orbit.utils import boto3_client, boto3_resource

_logger: logging.Logger = logging.getLogger(__name__)


def get_container_defaults() -> Dict[str, int]:
    return {"cpu": 4, "memory": 16384}


class SubnetKind(IntEnum):
    private: int = auto()
    public: int = auto()
    isolated: int = auto()


@dataclass(base_schema=BaseSchema)
class SubnetContext:
    Schema: ClassVar[Type[Schema]] = Schema
    subnet_id: str
    kind: SubnetKind
    vpc_id: str
    cidr_block: Optional[str] = None
    availability_zone: Optional[str] = None
    route_table_id: Optional[str] = None

    def _fetch_route_table_id(self) -> None:
        ec2_client = boto3_client("ec2")
        res: Dict[str, Any] = ec2_client.describe_route_tables(
            Filters=[{"Name": "association.subnet-id", "Values": [self.subnet_id]}]
        )
        for route_table in res["RouteTables"]:
            if "Associations" in route_table:
                for association in route_table["Associations"]:
                    if association["SubnetId"] == self.subnet_id:
                        self.route_table_id = association["RouteTableId"]
                        return

    def fetch_properties(self) -> None:
        try:
            ec2 = boto3_resource("ec2")
            subnet = ec2.Subnet(self.subnet_id)
            self.cidr_block = str(subnet.cidr_block)
            self.availability_zone = str(subnet.availability_zone)
            self.vpc_id = str(subnet.vpc_id)
            self._fetch_route_table_id()
            _logger.debug("Properties from subnet %s successfully fetched.", self.subnet_id)
        except botocore.exceptions.ClientError:
            _logger.debug("Unable to fetch properties from subnet (%s) right now.", self.subnet_id)


@dataclass(base_schema=BaseSchema)
class NetworkingContext:
    Schema: ClassVar[Type[Schema]] = Schema
    vpc_id: Optional[str] = None
    vpc_cidr_block: Optional[str] = None
    public_subnets: List[SubnetContext] = field(default_factory=list)
    private_subnets: List[SubnetContext] = field(default_factory=list)
    isolated_subnets: List[SubnetContext] = field(default_factory=list)
    availability_zones: Optional[List[str]] = None
    frontend: FrontendNetworkingManifest = FrontendNetworkingManifest()
    data: DataNetworkingManifest = DataNetworkingManifest()
    max_availability_zones: Optional[int] = None

    def _fetch_vpc_cidr(self) -> None:
        ec2 = boto3_resource("ec2")
        vpc = ec2.Vpc(self.vpc_id)
        self.vpc_cidr_block = str(vpc.cidr_block)

    def _fetch_subnets_properties(self) -> None:
        subnets = self.public_subnets + self.private_subnets + self.isolated_subnets
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(subnets)) as executor:
            list(executor.map(lambda s: cast(None, s.fetch_properties()), subnets))

    def fetch_properties(self) -> None:
        if self.vpc_id:
            self._fetch_vpc_cidr()
            self._fetch_subnets_properties()
            azs = sorted(
                list(
                    set(
                        s.availability_zone
                        for s in self.public_subnets + self.private_subnets + self.isolated_subnets
                        if s.availability_zone is not None
                    )
                )
            )
            self.availability_zones = azs if azs else None


@dataclass(base_schema=BaseSchema)
class TeamContext:
    Schema: ClassVar[Type[Schema]] = Schema

    # Manifest
    name: str
    policies: List[str]
    grant_sudo: bool
    jupyterhub_inbound_ranges: List[str]
    image: Optional[str]
    plugins: List[PluginManifest]
    profiles: List[Dict[str, Union[str, Dict[str, Any]]]]
    efs_life_cycle: Optional[str]

    # Context
    base_image_address: str
    final_image_address: str
    stack_name: str
    ssm_parameter_name: str
    team_ssm_parameter_name: str
    bootstrap_s3_prefix: str
    scratch_bucket: Optional[str] = None
    container_defaults: Dict[str, Any] = field(default_factory=get_container_defaults)
    efs_id: Optional[str] = None
    efs_ap_id: Optional[str] = None
    efs_private_ap_id: Optional[str] = None
    eks_pod_role_arn: Optional[str] = None
    jupyter_url: Optional[str] = None
    ecs_cluster_name: Optional[str] = None
    container_runner_arn: Optional[str] = None
    eks_k8s_api_arn: Optional[str] = None
    team_kms_key_arn: Optional[str] = None
    elbs: Optional[Dict[str, Dict[str, Any]]] = None
    team_security_group_id: Optional[str] = None
    # added with defaults for backward compatability
    fargate: bool = True
    k8_admin: bool = False
    team_helm_repository: Optional[str] = None
    user_helm_repository: Optional[str] = None

    # Manifest default
    authentication_groups: Optional[List[str]] = None

    def fetch_team_data(self) -> None:
        _logger.debug("Fetching Team %s data...", self.name)
        values = ssm.get_parameter(name=self.team_ssm_parameter_name)
        self.efs_id = values["EfsId"]
        self.efs_ap_id = values["EfsApId"]
        self.efs_private_ap_id = values["EfsApIdPrivate"]
        self.eks_pod_role_arn = values["EksPodRoleArn"]
        self.scratch_bucket = values["ScratchBucket"]
        self.team_kms_key_arn = values["TeamKmsKeyArn"]
        self.team_security_group_id = values["TeamSecurityGroupId"]


@dataclass(base_schema=BaseSchema)
class ToolkitManifest:
    stack_name: str
    codebuild_project: str
    deploy_id: Optional[str] = None
    admin_role: Optional[str] = None
    kms_arn: Optional[str] = None
    kms_alias: Optional[str] = None
    s3_bucket: Optional[str] = None


@dataclass(base_schema=BaseSchema)
class CdkToolkitManifest:
    stack_name: str
    s3_bucket: Optional[str] = None


@dataclass(base_schema=BaseSchema)
class FoundationContext:
    Schema: ClassVar[Type[Schema]] = Schema
    name: str
    account_id: str
    region: str
    env_tag: str
    toolkit: ToolkitManifest
    cdk_toolkit: CdkToolkitManifest
    networking: NetworkingContext = NetworkingContext()
    is_codeartifact_external: Optional[bool] = None
    user_pool_id: Optional[str] = None
    scratch_bucket_arn: Optional[str] = None
    cognito_users_url: Optional[str] = None
    cognito_external_provider_redirect: Optional[str] = None
    cognito_external_provider_domain: Optional[str] = None
    stack_name: Optional[str] = None
    ssm_parameter_name: Optional[str] = None
    resources_ssm_parameter_name: Optional[str] = None
    codeartifact_domain: Optional[str] = None
    codeartifact_repository: Optional[str] = None
    images: FoundationImagesManifest = FoundationImagesManifest()
    policies: Optional[List[str]] = cast(List[str], field(default_factory=list))
    orbit_version: Optional[str] = aws_orbit.__version__


@dataclass(base_schema=BaseSchema)
class Context:
    Schema: ClassVar[Type[Schema]] = Schema
    name: str
    account_id: str
    region: str
    env_tag: str
    env_stack_name: str
    env_ssm_parameter_name: str
    eks_stack_name: str
    ssm_parameter_name: str
    ssm_dockerhub_parameter_name: str
    toolkit: ToolkitManifest
    cdk_toolkit: CdkToolkitManifest
    networking: NetworkingContext
    user_pool_id: Optional[str] = None
    scratch_bucket_arn: Optional[str] = None
    cognito_users_url: Optional[str] = None
    cognito_external_provider_redirect: Optional[str] = None
    cognito_external_provider_domain: Optional[str] = None
    landing_page_url: Optional[str] = None
    k8_dashboard_url: Optional[str] = None
    codeartifact_domain: Optional[str] = None
    codeartifact_repository: Optional[str] = None
    cognito_external_provider: Optional[str] = None
    cognito_external_provider_label: Optional[str] = None
    eks_cluster_role_arn: Optional[str] = None
    eks_fargate_profile_role_arn: Optional[str] = None
    eks_env_nodegroup_role_arn: Optional[str] = None
    eks_oidc_provider: Optional[str] = None
    eks_system_masters_roles: Optional[List[str]] = cast(List[str], field(default_factory=list))
    user_pool_client_id: Optional[str] = None
    identity_pool_id: Optional[str] = None
    teams: List[TeamContext] = field(default_factory=list)
    images: ImagesManifest = ImagesManifest()
    elbs: Optional[Dict[str, Dict[str, Any]]] = None
    shared_efs_fs_id: Optional[str] = None
    shared_efs_sg_id: Optional[str] = None
    cluster_sg_id: Optional[str] = None
    cluster_pod_sg_id: Optional[str] = None
    managed_nodegroups: List[ManagedNodeGroupManifest] = field(default_factory=list)
    policies: Optional[List[str]] = cast(List[str], field(default_factory=list))
    orbit_version: Optional[str] = aws_orbit.__version__
    helm_repository: Optional[str] = None
    install_ssm_agent: Optional[bool] = False
    install_image_replicator: Optional[bool] = False

    def get_team_by_name(self, name: str) -> Optional[TeamContext]:
        for t in self.teams:
            if t.name == name:
                return t
        return None

    def remove_team_by_name(self, name: str) -> None:
        self.teams = [t for t in self.teams if t.name != name]

    def fetch_env_data(self) -> None:
        _logger.debug("Fetching Env data...")
        values = ssm.get_parameter(name=self.env_ssm_parameter_name)
        self.eks_cluster_role_arn = values["EksClusterRoleArn"]
        self.eks_fargate_profile_role_arn = values["EksFargateProfileRoleArn"]
        self.eks_env_nodegroup_role_arn = values["EksEnvNodegroupRoleArn"]
        self.user_pool_id = values["UserPoolId"]
        self.user_pool_client_id = values["UserPoolClientId"]
        self.identity_pool_id = values["IdentityPoolId"]
        self.cluster_pod_sg_id = values["ClusterPodSecurityGroupId"]
        self.fetch_cognito_external_idp_data()
        _logger.debug("Env data fetched successfully.")

    def fetch_cognito_external_idp_data(self) -> None:
        _logger.debug("Fetching Cognito External IdP data...")
        client = boto3_client(service_name="cognito-idp")
        response: Dict[str, Any] = client.describe_user_pool(UserPoolId=self.user_pool_id)
        domain: str = response["UserPool"].get("Domain")
        self.cognito_external_provider_domain = f"{domain}.auth.{self.region}.amazoncognito.com"
        _logger.debug("cognito_external_provider_domain: %s", self.cognito_external_provider_domain)
        response = client.describe_user_pool_client(UserPoolId=self.user_pool_id, ClientId=self.user_pool_client_id)
        self.cognito_external_provider_redirect = response["UserPoolClient"]["CallbackURLs"][0]
        _logger.debug("cognito_external_provider_redirect: %s", self.cognito_external_provider_redirect)
        _logger.debug("Cognito External IdP data fetched successfully.")

    def fetch_teams_data(self) -> None:
        _logger.debug("Fetching Teams data...")
        for team in self.teams:
            team.fetch_team_data()
        self.fetch_cognito_external_idp_data()
        _logger.debug("Env data fetched successfully.")


def create_team_context_from_manifest(manifest: "Manifest", team_manifest: "TeamManifest") -> TeamContext:
    account_id: str = utils.get_account_id()
    region: str = utils.get_region()
    ssm_parameter_name: str = f"/orbit/{manifest.name}/teams/{team_manifest.name}/context"
    version = manifest.images.jupyter_user.version
    _logger.debug("Team Base Image: %s - %s", team_manifest.name, manifest.images.jupyter_user)
    base_image_address = (
        f"{account_id}.dkr.ecr.{region}.amazonaws.com/orbit-{manifest.name}/jupyter-user:{version}"
        if manifest.images.jupyter_user.get_source(account_id=account_id, region=region) == "code"
        else f"{manifest.images.jupyter_user.repository}:{version}"
    )
    final_image_address = base_image_address
    return TeamContext(
        base_image_address=base_image_address,
        final_image_address=final_image_address,
        stack_name=f"orbit-{manifest.name}-{team_manifest.name}",
        ssm_parameter_name=ssm_parameter_name,
        team_ssm_parameter_name=f"/orbit/{manifest.name}/teams/{team_manifest.name}/team",
        bootstrap_s3_prefix=f"teams/{manifest.name}/bootstrap/",
        **team_manifest.__dict__,
    )


def create_teams_context_from_manifest(manifest: "Manifest") -> List[TeamContext]:
    teams: List[TeamContext] = []
    for team in manifest.teams:
        ssm_parameter_name: str = f"/orbit/{manifest.name}/teams/{team.name}/context"
        if ssm.does_parameter_exist(name=ssm_parameter_name) is False:
            _logger.debug("Team %s is not deployed yet.", team.name)
            continue
        teams.append(create_team_context_from_manifest(manifest=manifest, team_manifest=team))
    return teams


def create_networking_context_from_manifest(networking: "NetworkingManifest") -> NetworkingContext:
    args: Dict[str, Any] = {
        "frontend": networking.frontend,
        "data": networking.data,
        "max_availability_zones": networking.max_availability_zones,
    }
    if networking.vpc_id:
        args["vpc_id"] = networking.vpc_id
        args["public_subnets"] = [
            SubnetContext(subnet_id=x, kind=SubnetKind.public, vpc_id=networking.vpc_id)
            for x in networking.public_subnets
        ]
        args["private_subnets"] = [
            SubnetContext(subnet_id=x, kind=SubnetKind.private, vpc_id=networking.vpc_id)
            for x in networking.private_subnets
        ]
        args["isolated_subnets"] = [
            SubnetContext(subnet_id=x, kind=SubnetKind.isolated, vpc_id=networking.vpc_id)
            for x in networking.isolated_subnets
        ]
    ctx = NetworkingContext(**args)
    ctx.fetch_properties()
    return ctx


T = TypeVar("T")
V = TypeVar("V")


class ContextSerDe(Generic[T, V]):
    @staticmethod
    def load_context_from_manifest(manifest: T) -> V:
        if isinstance(manifest, Manifest):
            return cast(V, ContextSerDe._load_context_from_manifest(manifest))
        elif isinstance(manifest, FoundationManifest):
            return cast(V, ContextSerDe._load_foundation_context_from_manifest(manifest))
        else:
            raise ValueError("Unknown 'manifest' Type")

    @staticmethod
    def _load_context_from_manifest(manifest: "Manifest") -> Context:
        _logger.debug("Loading Context from manifest")
        context_parameter_name: str = f"/orbit/{manifest.name}/context"
        if ssm.does_parameter_exist(name=context_parameter_name):
            context: Context = ContextSerDe.load_context_from_ssm(env_name=manifest.name, type=Context)
            context.networking = create_networking_context_from_manifest(networking=manifest.networking)
            context.user_pool_id = manifest.user_pool_id
            context.shared_efs_fs_id = manifest.shared_efs_fs_id
            context.shared_efs_sg_id = manifest.shared_efs_sg_id
            context.scratch_bucket_arn = manifest.scratch_bucket_arn
            context.policies = manifest.policies
            context.codeartifact_domain = manifest.codeartifact_domain
            context.codeartifact_repository = manifest.codeartifact_repository
            context.cognito_external_provider = manifest.cognito_external_provider
            context.cognito_external_provider_label = manifest.cognito_external_provider_label
            for team_manifest in manifest.teams:
                team_context: Optional[TeamContext] = context.get_team_by_name(name=team_manifest.name)
                if team_context:
                    _logger.debug("Updating context profiles for team %s", team_manifest.name)
                    team_context.profiles = team_manifest.profiles
        else:
            context = Context(
                name=manifest.name,
                account_id=utils.get_account_id(),
                region=utils.get_region(),
                env_tag=f"orbit-{manifest.name}",
                env_stack_name=f"orbit-{manifest.name}",
                env_ssm_parameter_name=f"/orbit/{manifest.name}/env",
                eks_stack_name=f"eksctl-orbit-{manifest.name}-cluster",
                ssm_parameter_name=context_parameter_name,
                ssm_dockerhub_parameter_name=f"/orbit/{manifest.name}/dockerhub",
                toolkit=ToolkitManifest(
                    stack_name=f"orbit-{manifest.name}-toolkit", codebuild_project=f"orbit-{manifest.name}"
                ),
                cdk_toolkit=CdkToolkitManifest(stack_name=f"orbit-{manifest.name}-cdk-toolkit"),
                codeartifact_domain=manifest.codeartifact_domain,
                codeartifact_repository=manifest.codeartifact_repository,
                scratch_bucket_arn=manifest.scratch_bucket_arn,
                networking=create_networking_context_from_manifest(networking=manifest.networking),
                images=manifest.images,
                user_pool_id=manifest.user_pool_id,
                cognito_external_provider=manifest.cognito_external_provider,
                cognito_external_provider_label=manifest.cognito_external_provider_label,
                teams=create_teams_context_from_manifest(manifest=manifest),
                shared_efs_fs_id=manifest.shared_efs_fs_id,
                shared_efs_sg_id=manifest.shared_efs_sg_id,
                managed_nodegroups=[],
                eks_system_masters_roles=[],
                policies=manifest.policies,
                install_ssm_agent=manifest.install_ssm_agent,
                install_image_replicator=manifest.install_image_replicator,
            )
        context.install_ssm_agent = manifest.install_ssm_agent
        context.install_image_replicator = manifest.install_image_replicator

        ContextSerDe.fetch_toolkit_data(context=context)
        ContextSerDe.dump_context_to_ssm(context=context)
        return context

    @staticmethod
    def _load_foundation_context_from_manifest(manifest: "FoundationManifest") -> FoundationContext:
        _logger.debug("Loading Context from manifest")
        context_parameter_name: str = f"/orbit-f/{manifest.name}/context"
        if ssm.does_parameter_exist(name=context_parameter_name):
            context: FoundationContext = ContextSerDe.load_context_from_ssm(
                env_name=manifest.name, type=FoundationContext
            )
            context.images = manifest.images
            context.policies = manifest.policies
            context.codeartifact_domain = manifest.codeartifact_domain
            context.codeartifact_repository = manifest.codeartifact_repository
            context.networking = create_networking_context_from_manifest(networking=manifest.networking)
        else:
            context = FoundationContext(
                name=manifest.name,
                account_id=utils.get_account_id(),
                region=utils.get_region(),
                env_tag=f"orbit-f-{manifest.name}",
                ssm_parameter_name=context_parameter_name,
                resources_ssm_parameter_name=f"/orbit-f/{manifest.name}/resources",
                toolkit=ToolkitManifest(
                    stack_name=f"orbit-f-{manifest.name}-toolkit",
                    codebuild_project=f"orbit-f-{manifest.name}",
                ),
                cdk_toolkit=CdkToolkitManifest(stack_name=f"orbit-f-{manifest.name}-cdk-toolkit"),
                codeartifact_domain=manifest.codeartifact_domain,
                codeartifact_repository=manifest.codeartifact_repository,
                networking=create_networking_context_from_manifest(networking=manifest.networking),
                images=manifest.images,
                policies=manifest.policies,
                stack_name=f"orbit-f-{manifest.name}",
            )
        ContextSerDe.fetch_toolkit_data(context=context)
        ContextSerDe.dump_context_to_ssm(context=context)
        return context

    @staticmethod
    def dump_context_to_str(context: V) -> str:
        if isinstance(context, Context):
            content: Dict[str, Any] = cast(Dict[str, Any], Context.Schema().dump(context))
        elif isinstance(context, FoundationContext):
            content = cast(Dict[str, Any], FoundationContext.Schema().dump(context))
        elif isinstance(context, TeamContext):
            content = cast(Dict[str, Any], TeamContext.Schema().dump(context))
        else:
            raise ValueError("Unknown 'context' Type")
        return str(json.dumps(obj=content, sort_keys=True))

    def dump_context_to_ssm(context: V) -> None:
        _logger.debug("Writing context to SSM parameter.")

        if isinstance(context, Context):
            _logger.debug("Teams: %s", [t.name for t in context.teams])
            content: Dict[str, Any] = cast(Dict[str, Any], Context.Schema().dump(context))
            current_teams_contexts: List[str] = ssm.list_teams_contexts(env_name=context.name)
            written_teams_contexts: List[str] = []
            for team in content["Teams"]:
                ssm.put_parameter(name=team["SsmParameterName"], obj=team)
                written_teams_contexts.append(team["SsmParameterName"])
            old_teams_contexts: List[str] = list(set(current_teams_contexts) - set(written_teams_contexts))
            _logger.debug("old_teams_contexts: %s", old_teams_contexts)
            ssm.delete_parameters(parameters=old_teams_contexts)
            del content["Teams"]
            ssm_parameter_name = context.ssm_parameter_name
        elif isinstance(context, FoundationContext):
            content = cast(Dict[str, Any], FoundationContext.Schema().dump(context))
            ssm_parameter_name = cast(str, context.ssm_parameter_name)
        else:
            raise ValueError("Unknown 'context' Type")

        ssm.put_parameter(name=ssm_parameter_name, obj=content)
        _logger.debug("Context written to SSM: %s", content)

    @staticmethod
    def load_context_from_ssm(env_name: str, type: Type[V]) -> V:
        if type is Context:
            context_parameter_name: str = f"/orbit/{env_name}/context"
            if ssm.does_parameter_exist(context_parameter_name):
                main = ssm.get_parameter(name=context_parameter_name)
            else:
                msg = f"SSM parameter {context_parameter_name} not found for env {env_name}"
                _logger.error(msg)
                raise Exception(msg)
            _logger.debug("Raw SSM: %s", main)
            teams_parameters = ssm.list_parameters(prefix=f"/orbit/{env_name}/teams/")
            _logger.debug("teams_parameters: %s", teams_parameters)
            teams = [ssm.get_parameter_if_exists(name=p) for p in teams_parameters if p.endswith("/context")]
            main["Teams"] = [t for t in teams if t]
            return cast(V, Context.Schema().load(data=main, many=False, partial=False, unknown="EXCLUDE"))
        elif type is FoundationContext:
            context_parameter_name = f"/orbit-f/{env_name}/context"
            main = ssm.get_parameter(name=context_parameter_name)
            return cast(V, FoundationContext.Schema().load(data=main, many=False, partial=False, unknown="EXCLUDE"))
        else:
            raise ValueError("Unknown 'context' Type")

    @staticmethod
    def fetch_toolkit_data(context: V) -> None:
        _logger.debug("Fetching Toolkit data...")
        if not (isinstance(context, Context) or isinstance(context, FoundationContext)):
            raise ValueError("Unknown 'context' Type")

        top_level = "orbit" if isinstance(context, Context) else "orbit-f"

        resp_type = Dict[str, List[Dict[str, List[Dict[str, str]]]]]
        try:
            response: resp_type = boto3_client("cloudformation").describe_stacks(StackName=context.toolkit.stack_name)
            _logger.debug("%s stack found.", context.toolkit.stack_name)
        except botocore.exceptions.ClientError as ex:
            error: Dict[str, Any] = ex.response["Error"]
            if error["Code"] == "ValidationError" and f"{context.toolkit.stack_name} not found" in error["Message"]:
                _logger.debug("Toolkit stack not found.")
                return
            if (
                error["Code"] == "ValidationError"
                and f"{context.toolkit.stack_name} does not exist" in error["Message"]
            ):
                _logger.debug("Toolkit stack does not exist.")
                return
            raise
        if len(response["Stacks"]) < 1:
            _logger.debug("Toolkit stack not found.")
            return
        if "Outputs" not in response["Stacks"][0]:
            _logger.debug("Toolkit stack with empty outputs")
            return

        for output in response["Stacks"][0]["Outputs"]:
            if output["ExportName"] == f"{top_level}-{context.name}-deploy-id":
                _logger.debug("Export value: %s", output["OutputValue"])
                context.toolkit.deploy_id = output["OutputValue"]
            if output["ExportName"] == f"{top_level}-{context.name}-kms-arn":
                _logger.debug("Export value: %s", output["OutputValue"])
                context.toolkit.kms_arn = output["OutputValue"]
            if output["ExportName"] == f"{top_level}-{context.name}-admin-role":
                _logger.debug("Export value: %s", output["OutputValue"])
                context.toolkit.admin_role = output["OutputValue"]

        if context.toolkit.deploy_id is None:
            raise RuntimeError(
                f"Stack {context.toolkit.stack_name} does not have the expected {top_level}-{context.name}-deploy-id output."
            )
        if context.toolkit.kms_arn is None:
            raise RuntimeError(
                f"Stack {context.toolkit.stack_name} does not have the expected {top_level}-{context.name}-kms-arn output."
            )
        if context.toolkit.admin_role is None:
            raise RuntimeError(
                f"Stack {context.toolkit.stack_name} does not have the expected {top_level}-{context.name}-admin-role output."
            )

        context.toolkit.kms_alias = f"{top_level}-{context.name}-{context.toolkit.deploy_id}"
        context.toolkit.s3_bucket = (
            f"{top_level}-{context.name}-toolkit-{context.account_id}-{context.toolkit.deploy_id}"
        )
        context.cdk_toolkit.s3_bucket = (
            f"{top_level}-{context.name}-cdk-toolkit-{context.account_id}-{context.toolkit.deploy_id}"
        )

        if isinstance(context, Context):
            # Set the Helm repositories
            _logger.debug(f"context.helm_repository: s3://{context.toolkit.s3_bucket}/helm/repositories/env")
            context.helm_repository = f"s3://{context.toolkit.s3_bucket}/helm/repositories/env"

            _logger.debug("context.toolkit: %s", context.toolkit)

        _logger.debug("Toolkit data fetched successfully.")
