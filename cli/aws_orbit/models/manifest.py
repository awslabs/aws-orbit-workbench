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

import json
import logging
import os
import re
from typing import Any, ClassVar, Dict, Generic, List, Optional, Set, Type, TypeVar, Union, cast

import jsonpath_ng as jsonpath_ng
import yaml
from dataclasses import field
from marshmallow import EXCLUDE, Schema
from marshmallow_dataclass import dataclass
from yamlinclude import YamlIncludeConstructor

import aws_orbit
from aws_orbit import utils
from aws_orbit.models.common import BaseSchema
from aws_orbit.services import ssm
from aws_orbit.utils import boto3_client

_logger: logging.Logger = logging.getLogger(__name__)

SSM_CONTEXT: Dict[str, str] = {}


@dataclass(base_schema=BaseSchema, frozen=True)
class PluginManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    plugin_id: str
    module: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None


@dataclass(base_schema=BaseSchema, frozen=True)
class TeamManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    name: str
    policies: List[str] = field(default_factory=list)
    grant_sudo: bool = False
    fargate: bool = True
    k8_admin: bool = False
    jupyterhub_inbound_ranges: List[str] = field(default_factory=lambda: ["0.0.0.0/0"])
    image: Optional[str] = None
    plugins: List[PluginManifest] = field(default_factory=list)
    profiles: List[Dict[str, Union[str, Dict[str, Any]]]] = field(default_factory=list)
    efs_life_cycle: Optional[str] = None
    authentication_groups: Optional[List[str]] = None


@dataclass(base_schema=BaseSchema, frozen=True)
class ImageManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    repository: Optional[str]
    version: Optional[str] = "latest" if aws_orbit.__version__.endswith(".dev0") else aws_orbit.__version__
    path: Optional[str] = None

    def get_source(self, account_id: str, region: str) -> str:
        external_ecr_match = re.compile(r"^[0-9]{12}\.dkr\.ecr\..+\.amazonaws.com/")
        public_ecr_match = re.compile(r"^public.ecr.aws/.+/")
        repository = cast(str, self.repository)

        if self.path:
            return "code"
        elif repository.startswith(f"{account_id}.dkr.ecr.{region}.amazonaws.com"):
            return "ecr-internal"
        elif external_ecr_match.match(repository):
            return "ecr-external"
        elif public_ecr_match.match(repository):
            return "ecr-public"
        else:
            return "public"


@dataclass(base_schema=BaseSchema, frozen=True)
class ManagedNodeGroupManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    name: str
    instance_type: str = "m5.4xlarge"
    local_storage_size: int = 128
    nodes_num_desired: int = 2
    nodes_num_max: int = 3
    nodes_num_min: int = 1
    labels: Dict[str, str] = field(default_factory=dict)
    enable_virtual_gpu: bool = False
    availability_zones: Optional[List[str]] = None
    efa_enabled: Optional[bool] = None


@dataclass(base_schema=BaseSchema, frozen=True)
class CodeBuildImageManifest(ImageManifest):
    repository: Optional[str] = "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/code-build-base"
    version: Optional[str] = "1.1.0"


@dataclass(base_schema=BaseSchema, frozen=True)
class JupyterUserImageManifest(ImageManifest):
    repository: Optional[str] = "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/jupyter-user"


@dataclass(base_schema=BaseSchema, frozen=True)
class OrbitControllerImageManifest(ImageManifest):
    repository: Optional[str] = "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/orbit-controller"


@dataclass(base_schema=BaseSchema, frozen=True)
class K8sUtilitiesImageManifest(ImageManifest):
    repository: Optional[str] = "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/k8s-utilities"
    version: Optional[str] = "1.0.0"


@dataclass(base_schema=BaseSchema, frozen=True)
class UtilityDataImageManifest(ImageManifest):
    repository: Optional[str] = "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/utility-data"
    version: Optional[str] = "1.0.0"


@dataclass(base_schema=BaseSchema, frozen=True)
class FoundationImagesManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    code_build: CodeBuildImageManifest = CodeBuildImageManifest()
    names: List[str] = field(
        metadata=dict(load_only=True),
        default_factory=lambda: [
            "code_build",
        ],
    )


@dataclass(base_schema=BaseSchema, frozen=True)
class ImagesManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    code_build: ImageManifest = CodeBuildImageManifest()
    jupyter_user: ImageManifest = JupyterUserImageManifest()
    orbit_controller: ImageManifest = OrbitControllerImageManifest()
    k8s_utilities: ImageManifest = K8sUtilitiesImageManifest()
    utility_data: ImageManifest = UtilityDataImageManifest()
    names: List[str] = field(
        metadata=dict(load_only=True),
        default_factory=lambda: [
            "code_build",
            "jupyter_user",
            "orbit_controller",
            "k8s_utilities",
            "utility_data",
        ],
    )


@dataclass(base_schema=BaseSchema, frozen=True)
class FrontendNetworkingManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    load_balancers_subnets: List[str] = field(default_factory=list)
    ssl_cert_arn: Optional[str] = None
    custom_domain_name: Optional[str] = None


@dataclass(base_schema=BaseSchema, frozen=True)
class DataNetworkingManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    internet_accessible: bool = True
    nodes_subnets: List[str] = field(default_factory=list)


@dataclass(base_schema=BaseSchema, frozen=True)
class NetworkingManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    vpc_id: Optional[str] = None
    public_subnets: List[str] = field(default_factory=list)
    private_subnets: List[str] = field(default_factory=list)
    isolated_subnets: List[str] = field(default_factory=list)
    max_availability_zones: Optional[int] = None
    frontend: FrontendNetworkingManifest = FrontendNetworkingManifest()
    data: DataNetworkingManifest = DataNetworkingManifest()


@dataclass(base_schema=BaseSchema, frozen=True)
class FoundationManifest:
    Schema: ClassVar[Type[Schema]] = Schema
    name: str
    codeartifact_domain: Optional[str] = None
    codeartifact_repository: Optional[str] = None
    images: FoundationImagesManifest = FoundationImagesManifest()
    policies: Optional[List[str]] = cast(List[str], field(default_factory=list))
    ssm_parameter_name: Optional[str] = None
    networking: NetworkingManifest = NetworkingManifest()


@dataclass(base_schema=BaseSchema, frozen=True)
class Manifest:
    Schema: ClassVar[Type[Schema]] = Schema
    name: str
    user_pool_id: Optional[str] = None
    scratch_bucket_arn: Optional[str] = None
    eks_system_masters_roles: Optional[List[str]] = cast(List[str], field(default_factory=list))
    codeartifact_domain: Optional[str] = None
    codeartifact_repository: Optional[str] = None
    cognito_external_provider: Optional[str] = None
    cognito_external_provider_label: Optional[str] = None
    networking: NetworkingManifest = NetworkingManifest()
    teams: List[TeamManifest] = field(default_factory=list)
    images: ImagesManifest = ImagesManifest()
    shared_efs_fs_id: Optional[str] = None
    shared_efs_sg_id: Optional[str] = None
    managed_nodegroups: List[ManagedNodeGroupManifest] = field(default_factory=list)
    policies: Optional[List[str]] = cast(List[str], field(default_factory=list))
    ssm_parameter_name: Optional[str] = None
    install_ssm_agent: Optional[bool] = False
    install_image_replicator: Optional[bool] = False

    def get_team_by_name(self, name: str) -> Optional[TeamManifest]:
        for t in self.teams:
            if t.name == name:
                return t
        return None


def _add_ssm_param_injector(tag: str = "!SSM") -> Set[str]:
    """
    Load a yaml configuration file and resolve any SSM parameters
    The SSM parameters must have !SSM before them and be in this format
    to be parsed: ${SSM_PARAMETER_PATH::JSONPATH}.
    E.g.:
    database:
        host: !SSM ${/orbit-f/dev-env/resources::/UserAccessPolicy}
        port: !SSM ${/orbit-f/dev-env/resources::/PublicSubnet/*}
    """
    # pattern for global vars: look for ${word}
    pattern = re.compile(".*?\${([^}]+::[^}]*)}.*?")  # noqa: W605
    loader = yaml.SafeLoader

    # the tag will be used to mark where to start searching for the pattern
    # e.g. somekey: !SSM somestring${MYENVVAR}blah blah blah
    loader.add_implicit_resolver(tag, pattern, None)  # type: ignore

    ssm_parameters = set()

    def constructor_ssm_parameter(loader, node) -> Any:  # type: ignore
        """
        Extracts the environment variable from the node's value
        :param yaml.Loader loader: the yaml loader
        :param node: the current node in the yaml
        :return: the parsed string that contains the value of the environment
        variable
        """
        value = loader.construct_scalar(node)
        match = pattern.findall(value)  # to find all env variables in line
        if match:
            full_value = value
            for g in match:
                _logger.debug(f"match: {g}")
                (ssm_param_name, jsonpath) = g.split("::")
                if "${" in ssm_param_name:
                    ssm_param_name = ssm_param_name.replace("$", "").format(os.environ)
                _logger.debug(f"found injected parameter {(ssm_param_name, jsonpath)}")
                if ssm_param_name not in SSM_CONTEXT:
                    ssm = boto3_client("ssm")
                    try:
                        SSM_CONTEXT[ssm_param_name] = json.loads(
                            ssm.get_parameter(Name=ssm_param_name)["Parameter"]["Value"]
                        )
                        ssm_parameters.add(ssm_param_name)
                    except Exception as e:
                        _logger.error(f"Error resolving injected parameter {g}: {e}")

                json_expr = jsonpath_ng.parse(jsonpath)
                json_data = SSM_CONTEXT[ssm_param_name]
                json_match = json_expr.find(json_data)

                if len(json_match) > 1:
                    raise Exception(f"Injected parameter {g} is ambiguous")
                elif len(json_match) == 0:
                    raise Exception(f"Injected parameter {jsonpath} not found in SSM {ssm_param_name}")

                param_value: str = json_match[0].value
                _logger.debug(f"injected SSM parameter {g} resolved to {param_value}")
                return param_value
            return full_value
        return value

    loader.add_constructor(tag, constructor_ssm_parameter)  # type: ignore
    return ssm_parameters


def _add_env_var_injector(tag: str = "!ENV") -> None:
    """
    Load a yaml configuration file and resolve any environment variables
    The environment variables must have !ENV before them and be in this format
    to be parsed: ${VAR_NAME}.
    E.g.:
    database:
        host: !ENV ${HOST}
        port: !ENV ${PORT}
    app:
        log_path: !ENV '/var/${LOG_PATH}'
        something_else: !ENV '${AWESOME_ENV_VAR}/var/${A_SECOND_AWESOME_VAR}'
    """
    # pattern for global vars: look for ${word}
    pattern = re.compile(".*?\${([^}]+::[^}]*)}.*?")  # noqa: W605
    loader = yaml.SafeLoader

    # the tag will be used to mark where to start searching for the pattern
    # e.g. somekey: !ENV somestring${MYENVVAR}blah blah blah
    loader.add_implicit_resolver(tag, pattern, None)  # type: ignore

    def constructor_env_variables(loader, node) -> Any:  # type: ignore
        """
        Extracts the environment variable from the node's value
        :param yaml.Loader loader: the yaml loader
        :param node: the current node in the yaml
        :return: the parsed string that contains the value of the environment
        variable
        """
        value = loader.construct_scalar(node)
        match = pattern.findall(value)  # to find all env variables in line
        if match:
            full_value = value
            for g in match:
                (env_var, default_val) = g.split("::")
                value = os.environ.get(env_var, default_val)
                full_value = full_value.replace(f"${{{g}}}", value)
                if not full_value:
                    full_value = None
                _logger.debug(f"injected ENV parameter {env_var} resolved to {value}")
            return full_value
        return value

    loader.add_constructor(tag, constructor_env_variables)  # type: ignore


T = TypeVar("T")


class ManifestSerDe(Generic[T]):
    @staticmethod
    def load_manifest_from_file(filename: str, type: Type[T]) -> T:
        _logger.debug("Loading manifest file (%s)", filename)
        filepath = os.path.abspath(filename)
        _logger.debug("filepath: %s", filepath)
        filedir: str = os.path.dirname(filepath)
        utils.print_dir(dir=filedir)
        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.SafeLoader, base_dir=filedir)
        _add_ssm_param_injector()
        _add_env_var_injector()
        with open(filepath, "r") as f:
            raw: Dict[str, Any] = cast(Dict[str, Any], yaml.safe_load(f))
        _logger.debug("raw: %s", raw)
        if type is Manifest:
            raw["SsmParameterName"] = f"/orbit/{raw['Name']}/manifest"
            manifest: T = cast(T, Manifest.Schema().load(data=raw, many=False, partial=False, unknown=EXCLUDE))
        elif type is FoundationManifest:
            raw["SsmParameterName"] = f"/orbit-f/{raw['Name']}/manifest"
            manifest = cast(T, FoundationManifest.Schema().load(data=raw, many=False, partial=False, unknown=EXCLUDE))
        else:
            raise ValueError("Unknown 'manifest' Type")
        ManifestSerDe.dump_manifest_to_ssm(manifest=manifest)
        return manifest

    @staticmethod
    def dump_manifest_to_file(manifest: T, filepath: str) -> None:
        _logger.debug("Dumping manifest file (%s)", filepath)
        if isinstance(manifest, Manifest):
            content: Dict[str, Any] = cast(Dict[str, Any], Manifest.Schema().dump(manifest))
        elif isinstance(manifest, FoundationManifest):
            content = cast(Dict[str, Any], FoundationManifest.Schema().dump(manifest))
        else:
            raise ValueError("Unknown 'manifest' Type")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            yaml.dump(content, f, sort_keys=False)

    @staticmethod
    def dump_manifest_to_ssm(manifest: T) -> None:
        _logger.debug("Writing manifest to SSM parameter.")

        if isinstance(manifest, Manifest):
            _logger.debug("Teams: %s", [t.name for t in manifest.teams])
            content: Dict[str, Any] = cast(Dict[str, Any], Manifest.Schema().dump(manifest))
            ssm.cleanup_manifest(env_name=manifest.name)
            if "Teams" in content:
                for team in content["Teams"]:
                    team_parameter_name: str = f"/orbit/{manifest.name}/teams/{team['Name']}/manifest"
                    ssm.put_parameter(name=team_parameter_name, obj=team)
                del content["Teams"]
            manifest_parameter_name = manifest.ssm_parameter_name
        elif isinstance(manifest, FoundationManifest):
            content = cast(Dict[str, Any], FoundationManifest.Schema().dump(manifest))
            ssm.cleanup_manifest(env_name=manifest.name, top_level="orbit-f")
            manifest_parameter_name = manifest.ssm_parameter_name
        else:
            raise ValueError("Unknown 'manifest' Type")

        ssm.put_parameter(name=cast(str, manifest_parameter_name), obj=content)

    @staticmethod
    def load_manifest_from_ssm(env_name: str, type: Type[T]) -> Optional[T]:
        if type is Manifest:
            context_parameter_name = f"/orbit/{env_name}/manifest"
            main = ssm.get_parameter_if_exists(name=context_parameter_name)
            if main is None:
                return None
            teams_parameters = ssm.list_parameters(prefix=f"/orbit/{env_name}/teams/")
            _logger.debug("teams_parameters (/orbit/%s/teams/): %s", env_name, teams_parameters)
            teams = [ssm.get_parameter(name=p) for p in teams_parameters if p.endswith("/manifest")]
            main["Teams"] = teams
            return cast(T, Manifest.Schema().load(data=main, many=False, partial=False, unknown=EXCLUDE))
        elif type is FoundationManifest:
            context_parameter_name = f"/orbit-f/{env_name}/manifest"
            main = ssm.get_parameter_if_exists(name=context_parameter_name)
            if main is None:
                return None
            return cast(T, FoundationManifest.Schema().load(data=main, many=False, partial=False, unknown=EXCLUDE))
        else:
            raise ValueError("Unknown 'manifest' Type")


def manifest_validations(manifest: Manifest) -> None:
    for managed_nodegroup in manifest.managed_nodegroups:
        _logger.debug(f"Validating managed node group {managed_nodegroup} ")
        if managed_nodegroup.nodes_num_desired < 1:
            raise ValueError(f"{managed_nodegroup.name}  number of desired nodes should be greater than 0")
