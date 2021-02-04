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

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union, cast

import boto3
import botocore.config
import botocore.exceptions
import jsonpath_ng as jsonpath_ng
import yaml
from yamlinclude import YamlIncludeConstructor

from aws_orbit import utils
from aws_orbit.manifest import team as manifest_team
from aws_orbit.manifest.subnet import SubnetKind, SubnetManifest
from aws_orbit.manifest.team import MANIFEST_FILE_TEAM_TYPE, MANIFEST_TEAM_TYPE, TeamManifest, parse_teams
from aws_orbit.manifest.vpc import MANIFEST_FILE_VPC_TYPE, MANIFEST_VPC_TYPE, VpcManifest, parse_vpc

_logger: logging.Logger = logging.getLogger(__name__)
MANIFEST_PROPERTY_MAP_TYPE = Dict[str, Union[str, Dict[str, Any]]]
MANIFEST_FILE_IMAGES_TYPE = Dict[str, Dict[str, str]]
MANIFEST_FILE_NETWORKING_TYPE = Dict[str, Dict[str, Union[bool, List[str]]]]
MANIFEST_FILE_TYPE = Dict[
    str,
    Union[
        str,
        bool,
        List[str],
        MANIFEST_FILE_VPC_TYPE,
        List[MANIFEST_FILE_TEAM_TYPE],
        MANIFEST_FILE_IMAGES_TYPE,
        MANIFEST_FILE_NETWORKING_TYPE,
    ],
]
MANIFEST_TYPE = Dict[
    str,
    Union[
        None,
        str,
        bool,
        MANIFEST_VPC_TYPE,
        List[str],
    ],
]

MANIFEST_FILE_IMAGES_DEFAULTS: MANIFEST_FILE_IMAGES_TYPE = cast(
    MANIFEST_FILE_IMAGES_TYPE,
    {
        "jupyter-hub": {
            "repository": "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/jupyter-hub",
            "source": "ecr",
            "version": "latest",
        },
        "jupyter-user": {
            "repository": "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/jupyter-user",
            "source": "ecr",
            "version": "latest",
        },
        "jupyter-user-spark": {
            "repository": "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/jupyter-user-spark",
            "source": "ecr",
            "version": "latest",
        },
        "landing-page": {
            "repository": "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/landing-page",
            "source": "ecr",
            "version": "latest",
        },
        "aws-efs-csi-driver": {
            "repository": "602401143452.dkr.ecr.us-west-2.amazonaws.com/eks/aws-efs-csi-driver",
            "source": "ecr-external",
            "version": "v1.0.0",
        },
        "livenessprobe": {
            "repository": "602401143452.dkr.ecr.us-west-2.amazonaws.com/eks/livenessprobe",
            "source": "ecr-external",
            "version": "v2.0.0",
        },
        "csi-node-driver-registrar": {
            "repository": "602401143452.dkr.ecr.us-west-2.amazonaws.com/eks/csi-node-driver-registrar",
            "source": "ecr-external",
            "version": "v1.3.0",
        },
        "code-build-image": {
            "repository": "public.ecr.aws/v3o4w1g6/aws-orbit-workbench/code-build-base",
            "source": "ecr",
            "version": "latest",
        },
    },
)

ssm_context: Dict[str, str] = {}


class Manifest:
    def __init__(self, filename: Optional[str], env: Optional[str], region: Optional[str]) -> None:
        self.name: str
        self.ssm_parameter_name: str
        self.cognito_external_provider_label: Optional[str]
        self.cognito_external_provider: Optional[str]
        self.internet_accessible: bool
        self.codeartifact_domain: Optional[str]
        self.images: MANIFEST_FILE_IMAGES_TYPE
        self.teams: List[TeamManifest]
        self.load_balancers_subnets: List[str]
        self.eks_system_masters_roles: List[str]
        self.scratch_bucket_arn: Optional[str]
        self.shared_efs_fs_id: Optional[str]
        self.shared_efs_sg_id: Optional[str]
        self.user_pool_id: Optional[str]
        if filename and env:
            raise RuntimeError("Must provide either a manifest file or environment name and neither were provided.")
        if region:
            self.region: str = region
        else:
            self.region = utils.get_region()
        self.account_id: str = self.get_account_id()
        # Need to fill up
        self.deploy_id: Optional[str] = None  # toolkit
        self.toolkit_kms_arn: Optional[str] = None  # toolkit
        self.toolkit_kms_alias: Optional[str] = None  # toolkit
        self.toolkit_s3_bucket: Optional[str] = None  # toolkit
        self.cdk_toolkit_s3_bucket: Optional[str] = None  # toolkit

        self.raw_ssm: Optional[MANIFEST_TYPE] = None  # Env
        self.eks_cluster_role_arn: Optional[str] = None  # Env
        self.eks_fargate_profile_role_arn: Optional[str] = None  # Env
        self.eks_env_nodegroup_role_arn: Optional[str] = None  # Env
        self.eks_oidc_provider: Optional[str] = None  # Env
        self.user_pool_client_id: Optional[str] = None  # Env
        self.identity_pool_id: Optional[str] = None  # Env
        self.cognito_users_urls: Optional[str] = None  # Env
        self.landing_page_url: Optional[str] = None  # Kubectl
        self.elbs: Optional[Dict[str, Dict[str, Any]]] = None  # Kubectl

        self.cognito_external_provider_domain: Optional[str] = None  # Cognito
        self.cognito_external_provider_redirect: Optional[str] = None  # Cognito

        if filename:
            self.load_manifest_from_file(filename)
        elif env:
            self.load_manifest_from_ssm(env)
        else:
            raise RuntimeError("Must provide either a manifest file or environment name and neither were provided.")

        self.env_tag: str = f"orbit-{self.name}"
        self.ssm_dockerhub_parameter_name: str = f"/orbit/{self.name}/dockerhub"
        self.toolkit_stack_name: str = f"orbit-{self.name}-toolkit"
        self.cdk_toolkit_stack_name: str = f"orbit-{self.name}-cdk-toolkit"
        self.demo_stack_name: str = f"orbit-{self.name}-demo"
        self.env_stack_name: str = f"orbit-{self.name}"
        self.eks_stack_name: str = f"eksctl-{self.env_stack_name}-cluster"
        self.toolkit_codebuild_project: str = f"orbit-{self.name}"

    def load_manifest_from_ssm(self, env: str) -> None:
        self.name = env
        self.ssm_parameter_name = f"/orbit/{self.name}/manifest"
        self.fetch_ssm()
        _logger.debug("Loaded manifest from SSM %s", self.ssm_parameter_name)

    def load_manifest_from_file(self, filename: str) -> None:
        self.filename: str = filename
        self.filename_dir: str = utils.path_from_filename(filename=filename)
        self.raw_file: MANIFEST_FILE_TYPE = self._read_manifest_file(filename=filename)
        self.name = cast(str, self.raw_file["name"])
        self.ssm_parameter_name = f"/orbit/{self.name}/manifest"
        self.eks_system_masters_roles = cast(List[str], self.raw_file.get("eks-system-masters-roles", []))
        self.scratch_bucket_arn = cast(str, self.raw_file.get("scratch-bucket-arn"))
        self.shared_efs_fs_id = cast(Optional[str], self.raw_file.get("shared-efs-fs-id"))
        self.shared_efs_sg_id = cast(Optional[str], self.raw_file.get("shared-efs-sg-id"))

        self.user_pool_id = cast(Optional[str], self.raw_file.get("user-pool-id"))
        # Networking
        if "networking" not in self.raw_file:
            raise RuntimeError("Invalid manifest: Missing the 'networking' attribute.")
        self.networking: Dict[str, Any] = cast(Dict[str, Any], self.raw_file["networking"])
        if "data" not in self.networking:
            raise RuntimeError("Invalid manifest: Missing the 'data' attribute under 'networking'.")
        if "frontend" not in self.networking:
            raise RuntimeError("Invalid manifest: Missing the 'frontend' attribute under 'networking'.")
        self.internet_accessible = cast(bool, self.networking["data"].get("internet-accessible", True))
        self.nodes_subnets: List[str] = cast(List[str], self.networking["data"].get("nodes-subnets", []))
        self.load_balancers_subnets = cast(List[str], self.networking["frontend"].get("load-balancers-subnets", []))

        self.codeartifact_domain = cast(Optional[str], self.raw_file.get("codeartifact-domain", None))
        self.codeartifact_repository: Optional[str] = cast(
            Optional[str], self.raw_file.get("codeartifact-repository", None)
        )
        # Images
        if self.raw_file.get("images") is None:
            self.images = MANIFEST_FILE_IMAGES_DEFAULTS
        else:
            self.images = cast(MANIFEST_FILE_IMAGES_TYPE, self.raw_file["images"])
            for k, v in MANIFEST_FILE_IMAGES_DEFAULTS.items():  # Filling missing images
                if k not in self.images:
                    self.images[k] = v

        self.vpc: VpcManifest = parse_vpc(manifest=self)
        if "teams" in self.raw_file and hasattr(self, "raw_file"):
            self.teams = parse_teams(
                manifest=self, raw_teams=cast(List[MANIFEST_FILE_TEAM_TYPE], self.raw_file["teams"])
            )
            _logger.debug("Teams loaded: %s", [t.name for t in self.teams])
        else:
            self.teams = []

        self.cognito_external_provider = cast(Optional[str], self.raw_file.get("external-idp", None))
        self.cognito_external_provider_label = cast(Optional[str], self.raw_file.get("external-idp-label", None))

    def get_account_id(self) -> str:
        return str(self.boto3_client(service_name="sts").get_caller_identity().get("Account"))

    @staticmethod
    def _read_manifest_file(filename: str) -> MANIFEST_FILE_TYPE:
        _logger.debug("reading manifest file (%s)", filename)
        filename = os.path.abspath(filename)
        conf_dir = os.path.dirname(filename)
        manifest_path = os.path.join(conf_dir, os.path.basename(filename))
        _logger.debug("manifest: %s", manifest_path)
        YamlIncludeConstructor.add_to_loader_class(loader_class=yaml.SafeLoader, base_dir=conf_dir)
        Manifest._add_env_var_injector()
        Manifest._add_ssm_param_injector()
        with open(manifest_path, "r") as f:
            return cast(MANIFEST_FILE_TYPE, yaml.safe_load(f))

    @staticmethod
    def _add_ssm_param_injector(tag: str = "!SSM") -> None:
        """
        Load a yaml configuration file and resolve any SSM parameters
        The SSM parameters must have !SSM before them and be in this format
        to be parsed: ${SSM_PARAMETER_PATH::JSONPATH}.
        E.g.:
        database:
            host: !SSM ${/orbit/dev-env/demo::/UserAccessPolicy}
            port: !SSM ${/orbit/dev-env/demo::/PublicSubnet/*}
        """
        # pattern for global vars: look for ${word}
        pattern = re.compile(".*?\${(.*)}.*?")  # noqa: W605
        loader = yaml.SafeLoader

        # the tag will be used to mark where to start searching for the pattern
        # e.g. somekey: !SSM somestring${MYENVVAR}blah blah blah
        loader.add_implicit_resolver(tag, pattern, None)  # type: ignore

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
                    (ssm_param_name, jsonpath) = g.split("::")
                    _logger.debug(f"found injected parameter {(ssm_param_name, jsonpath)}")
                    if ssm_param_name not in ssm_context:
                        ssm = utils.boto3_client("ssm")
                        try:
                            ssm_context[ssm_param_name] = json.loads(
                                ssm.get_parameter(Name=ssm_param_name)["Parameter"]["Value"]
                            )
                            print(ssm_context[ssm_param_name])
                        except Exception as e:
                            _logger.error(f"Error resolving injected parameter {g}: {e}")
                            pass

                    json_expr = jsonpath_ng.parse(jsonpath)
                    json_data = ssm_context[ssm_param_name]
                    json_match = json_expr.find(json_data)

                    if len(json_match) > 1:
                        raise Exception(f"Injected parameter {g} is ambiguous")
                    elif len(json_match) == 0:
                        raise Exception(f"Injected parameter {jsonpath} not found in SSM {ssm_param_name}")

                    param_value: str = json_match[0].value
                    _logger.debug(f"injected parameter {g} resolved to {param_value}")
                    # full_value = full_value.replace(f"${{{g}}}", str(param_value))
                    return param_value
                return full_value
            return value

        loader.add_constructor(tag, constructor_ssm_parameter)  # type: ignore

    @staticmethod
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
        pattern = re.compile(".*?\${(\w+)}.*?")  # noqa: W605
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
                    full_value = full_value.replace(f"${{{g}}}", os.environ.get(g, g))
                return full_value
            return value

        loader.add_constructor(tag, constructor_env_variables)  # type: ignore

    @staticmethod
    def _botocore_config() -> botocore.config.Config:
        return botocore.config.Config(retries={"max_attempts": 5}, connect_timeout=10, max_pool_connections=10)

    def _boto3_session(self) -> boto3.Session:
        return boto3.Session(region_name=self.region)

    def _read_manifest_ssm(self) -> Optional[MANIFEST_TYPE]:
        _logger.debug("Trying to read manifest from SSM parameter.")
        client = self.boto3_client(service_name="ssm")
        try:
            json_str: str = client.get_parameter(Name=self.ssm_parameter_name)["Parameter"]["Value"]
        except client.exceptions.ParameterNotFound:
            _logger.debug("Manifest SSM parameter not found.")
            return None
        _logger.debug("Manifest SSM parameter found.")
        return cast(MANIFEST_TYPE, json.loads(json_str))

    def write_manifest_ssm(self) -> None:
        client = self.boto3_client(service_name="ssm")
        _logger.debug("Writing manifest to SSM parameter.")
        _logger.debug("Teams: %s", [t.name for t in self.teams])
        try:
            client.get_parameter(Name=self.ssm_parameter_name)["Parameter"]["Value"]
            exists: bool = True
        except client.exceptions.ParameterNotFound:
            exists = False
        _logger.debug("Does Manifest SSM parameter exist? %s", exists)
        if exists:
            client.put_parameter(
                Name=self.ssm_parameter_name,
                Value=self.asjson(),
                Overwrite=True,
                Tier="Intelligent-Tiering",
            )

    def write_manifest_file(self) -> None:
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "w") as file:
            yaml.safe_dump(data=self.asdict_file(), stream=file, sort_keys=False, indent=4)
        _logger.debug("Manifest file updated: %s", os.path.abspath(self.filename))

    def boto3_client(self, service_name: str) -> boto3.client:
        return self._boto3_session().client(service_name=service_name, use_ssl=True, config=self._botocore_config())

    def boto3_resource(self, service_name: str) -> boto3.client:
        return self._boto3_session().resource(service_name=service_name, use_ssl=True, config=self._botocore_config())

    def fetch_ssm(self) -> bool:
        _logger.debug("Fetching SSM manifest data...")
        self.raw_ssm = self._read_manifest_ssm()
        if self.raw_ssm is not None:
            raw: MANIFEST_TYPE = self.raw_ssm
            self.landing_page_url = cast(Optional[str], raw.get("landing-page-url"))
            self.elbs = cast(Optional[Dict[str, Dict[str, Any]]], raw.get("elbs"))
            self.deploy_id = cast(Optional[str], raw.get("deploy-id"))
            self.toolkit_s3_bucket = cast(Optional[str], raw.get("toolkit-s3-bucket"))
            self.toolkit_kms_alias = cast(Optional[str], raw.get("toolkit-kms-alias"))
            self.toolkit_kms_arn = cast(Optional[str], raw.get("toolkit-kms-arn"))
            self.cdk_toolkit_s3_bucket = cast(Optional[str], raw.get("cdk-toolkit-s3-bucket"))
            self.eks_cluster_role_arn = cast(Optional[str], raw.get("eks-cluster-role-arn"))
            self.eks_fargate_profile_role_arn = cast(Optional[str], raw.get("eks-fargate-profile-role-arn"))
            self.eks_env_nodegroup_role_arn = cast(Optional[str], raw.get("eks-env-nodegroup-role-arn"))
            self.eks_oidc_provider = cast(Optional[str], raw.get("eks-oidc-provider"))
            self.eks_system_masters_roles = cast(List[str], raw.get("eks-system-masters-roles", []))
            self.user_pool_client_id = cast(Optional[str], raw.get("user-pool-client-id"))
            self.scratch_bucket_arn = cast(Optional[str], raw.get("scratch-bucket-arn"))
            self.identity_pool_id = cast(Optional[str], raw.get("identity-pool-id"))
            self.cognito_external_provider = cast(Optional[str], raw.get("cognito-external-provider", None))
            self.cognito_external_provider_label = cast(Optional[str], raw.get("cognito-external-provider-label", None))
            self.cognito_external_provider_domain = cast(Optional[str], raw.get("cognito-external-provider-domain"))
            self.cognito_external_provider_redirect = cast(Optional[str], raw.get("cognito-external-provider-redirect"))
            self.shared_efs_fs_id = cast(Optional[str], raw.get("shared-efs-fs-id"))
            self.shared_efs_sg_id = cast(Optional[str], raw.get("shared-efs-sg-id"))
            self.internet_accessible = cast(bool, raw.get("internet-accessible", False))
            self.codeartifact_domain = cast(Optional[str], raw.get("codeartifact-domain", None))
            self.codeartifact_repository = cast(Optional[str], raw.get("codeartifact-repository", None))
            self.images = cast(MANIFEST_FILE_IMAGES_TYPE, raw.get("images"))
            self.load_balancers_subnets = cast(List[str], raw.get("load-balancers-subnets"))
            self.user_pool_id = cast(Optional[str], raw.get("user-pool-id"))
            if not hasattr(self, "vpc"):
                raw_vpc = cast("MANIFEST_VPC_TYPE", raw.get("vpc"))
                subnets_raw: List[Dict[str, str]] = cast(List[Dict[str, str]], raw_vpc.get("subnets"))
                subnets: List[SubnetManifest] = [
                    SubnetManifest(manifest=self, subnet_id=s["subnet-id"], kind=SubnetKind[s["kind"]])
                    for s in subnets_raw
                ]
                self.vpc = VpcManifest(manifest=self, subnets=subnets)

            self.vpc.fillup_from_ssm()
            if not hasattr(self, "teams"):
                teams: List[str] = cast(List[str], raw.get("teams"))
                raw_old_teams: List["MANIFEST_TEAM_TYPE"] = []
                for name in teams:
                    raw_team = manifest_team.read_raw_manifest_ssm(manifest=self, team_name=name)
                    if raw_team is None:
                        # ignore this team because it was deleted but not yet updated in the main manifest
                        _logger.debug(f"Found {name} in main manifest but without its own SSM. Ignoring")
                        continue
                    raw_old_teams.append(raw_team)

                self.teams = manifest_team.parse_teams(
                    manifest=self, raw_teams=cast(List["MANIFEST_FILE_TEAM_TYPE"], raw_old_teams)
                )
            else:
                for team in self.teams:
                    team.fetch_ssm()

            _logger.debug("Env %s loaded successfully from SSM.", self.name)
            return True
        return False

    def fetch_toolkit_data(self) -> None:
        _logger.debug("Fetching Toolkit data...")
        self.fetch_ssm()
        resp_type = Dict[str, List[Dict[str, List[Dict[str, str]]]]]

        try:
            response: resp_type = self.boto3_client("cloudformation").describe_stacks(StackName=self.toolkit_stack_name)
        except botocore.exceptions.ClientError as ex:
            error: Dict[str, Any] = ex.response["Error"]
            if error["Code"] == "ValidationError" and f"{self.toolkit_stack_name} does not exist" in error["Message"]:
                logging.debug("Toolkit stack not found.")
                return
            raise
        if len(response["Stacks"]) < 1:
            logging.debug("Toolkit stack not found.")
            return
        if "Outputs" not in response["Stacks"][0]:
            logging.debug("Toolkit stack with empty outputs")
            return

        for output in response["Stacks"][0]["Outputs"]:
            if output["ExportName"] == f"orbit-{self.name}-deploy-id":
                _logger.debug("Export value: %s", output["OutputValue"])
                self.deploy_id = output["OutputValue"]
            if output["ExportName"] == f"orbit-{self.name}-kms-arn":
                _logger.debug("Export value: %s", output["OutputValue"])
                self.toolkit_kms_arn = output["OutputValue"]
        if self.deploy_id is None:
            raise RuntimeError(
                f"Stack {self.toolkit_stack_name} does not have the expected orbit-{self.name}-deploy-id output."
            )
        if self.toolkit_kms_arn is None:
            raise RuntimeError(
                f"Stack {self.toolkit_stack_name} does not have the expected orbit-{self.name}-kms-arn output."
            )
        self.toolkit_kms_alias = f"orbit-{self.name}-{self.deploy_id}"
        self.toolkit_s3_bucket = f"orbit-{self.name}-toolkit-{self.account_id}-{self.deploy_id}"
        self.cdk_toolkit_s3_bucket = f"orbit-{self.name}-cdk-toolkit-{self.account_id}-{self.deploy_id}"
        self.write_manifest_ssm()
        _logger.debug("Toolkit data fetched successfully.")

    def fetch_demo_data(self) -> None:
        _logger.debug("Fetching DEMO data...")
        resp_type = Dict[str, List[Dict[str, List[Dict[str, str]]]]]

        try:
            response: resp_type = self.boto3_client("cloudformation").describe_stacks(StackName=self.demo_stack_name)
        except botocore.exceptions.ClientError as ex:
            error: Dict[str, Any] = ex.response["Error"]
            if error["Code"] == "ValidationError" and f"{self.demo_stack_name} does not exist" in error["Message"]:
                logging.debug("DEMO stack not found.")
                return
            raise
        if len(response["Stacks"]) < 1:
            logging.debug("DEMO stack not found.")
            return
        if "Outputs" not in response["Stacks"][0]:
            logging.debug("DEMO stack with empty outputs")
            return

        vpc_id = None
        for output in response["Stacks"][0]["Outputs"]:
            if output["ExportName"] == f"orbit-{self.name}-nodes-subnet-ids":
                self.nodes_subnets = output["OutputValue"].split(",")
            elif output["ExportName"] == f"orbit-{self.name}-public-subnet-ids":
                self.load_balancers_subnets = output["OutputValue"].split(",")
            elif output["ExportName"] == f"orbit-{self.name}-vpc-id":
                vpc_id = output["OutputValue"]

        self.vpc = parse_vpc(manifest=self)
        self.vpc.vpc_id = vpc_id

        # self.fetch_ssm()
        # self.write_manifest_ssm()
        _logger.debug("DEMO data fetched successfully.")

    def fetch_network_data(self) -> None:
        _logger.debug("Fetching network data...")
        self.fetch_ssm()
        self.vpc.fetch_properties()
        self.write_manifest_ssm()
        _logger.debug("Network data fetched successfully.")

    def fetch_cognito_external_idp_data(self) -> None:
        if self.cognito_external_provider is not None and self.user_pool_id is not None:
            _logger.debug("Fetching Cognito External IdP data...")
            self.fetch_ssm()
            client = self.boto3_client(service_name="cognito-idp")
            response: Dict[str, Any] = client.describe_user_pool(UserPoolId=self.user_pool_id)
            domain: str = response["UserPool"]["Domain"]
            self.cognito_external_provider_domain = f"{domain}.auth.{self.region}.amazoncognito.com"
            _logger.debug("cognito_external_provider_domain: %s", self.cognito_external_provider_domain)
            response = client.describe_user_pool_client(UserPoolId=self.user_pool_id, ClientId=self.user_pool_client_id)
            self.cognito_external_provider_redirect = response["UserPoolClient"]["CallbackURLs"][0]
            _logger.debug("cognito_external_provider_redirect: %s", self.cognito_external_provider_redirect)
            self.write_manifest_ssm()
            _logger.debug("Cognito External IdP data fetched successfully.")

    def fillup(self) -> None:
        if self.fetch_ssm() is False:
            self.fetch_toolkit_data()
            # self.fetch_demo_data()
            self.fetch_network_data()
            self.fetch_cognito_external_idp_data()

    def asdict_file(self) -> MANIFEST_FILE_TYPE:
        obj: MANIFEST_FILE_TYPE = {
            "name": self.name,
            "region": self.region,
            "networking": {
                "data": cast(
                    Dict[str, Union[bool, List[str]]],
                    {"internet-accessible": self.internet_accessible, "nodes-subnets": self.nodes_subnets},
                ),
                "frontend": cast(
                    Dict[str, Union[bool, List[str]]], {"load-balancers-subnets": self.load_balancers_subnets}
                ),
            },
        }
        if self.codeartifact_domain is not None:
            obj["codeartifact-domain"] = self.codeartifact_domain
        if self.codeartifact_repository is not None:
            obj["codeartifact-repository"] = self.codeartifact_repository
        if self.cognito_external_provider is not None:
            obj["external-idp"] = self.cognito_external_provider
        if self.cognito_external_provider_label is not None:
            obj["external-idp-label"] = self.cognito_external_provider_label
        if self.user_pool_id is not None:
            obj["user-pool-id"] = self.user_pool_id
        if self.shared_efs_fs_id is not None:
            obj["shared-efs-fs-id"] = self.shared_efs_fs_id
        if self.shared_efs_sg_id is not None:
            obj["shared-efs-sg-id"] = self.shared_efs_sg_id
        if self.scratch_bucket_arn is not None:
            obj["scratch-bucket-arn"] = self.scratch_bucket_arn
        obj["images"] = self.images
        obj["teams"] = [t.asdict_file() for t in self.teams]
        obj["eks-system-masters-roles"] = self.eks_system_masters_roles
        return obj

    def asdict(self) -> MANIFEST_TYPE:
        obj: MANIFEST_TYPE = utils.replace_underscores(vars(self))
        obj["vpc"] = self.vpc.asdict()
        obj["teams"] = [t.name for t in self.teams]
        if "filename" in obj:
            del obj["filename"]
        if "filename-dir" in obj:
            del obj["filename-dir"]
        if "raw-ssm" in obj:
            del obj["raw-ssm"]
        if "raw-file" in obj:
            del obj["raw-file"]
        if "networking" in obj:
            del obj["networking"]
        return obj

    def asjson(self) -> str:
        return str(json.dumps(obj=self.asdict(), sort_keys=True))


def get_team_by_name(teams: List["TeamManifest"], name: str) -> Optional["TeamManifest"]:
    for t in teams:
        if t.name == name:
            return t
    return None
