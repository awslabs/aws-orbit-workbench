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
from typing import Any, Dict, List, Optional, Union, cast

import boto3
import botocore.config
import botocore.exceptions
import yaml

from datamaker_cli import utils
from datamaker_cli.manifest.plugin import MANIFEST_FILE_PLUGIN_TYPE, PluginManifest
from datamaker_cli.manifest.subnet import MANIFEST_FILE_SUBNET_TYPE, SubnetKind, SubnetManifest
from datamaker_cli.manifest.team import MANIFEST_FILE_TEAM_TYPE, MANIFEST_TEAM_TYPE, TeamManifest
from datamaker_cli.manifest.vpc import MANIFEST_FILE_VPC_TYPE, MANIFEST_VPC_TYPE, VpcManifest
from datamaker_cli.services import cognito

_logger: logging.Logger = logging.getLogger(__name__)

MANIFEST_FILE_IMAGES_TYPE = Dict[str, Dict[str, str]]
MANIFEST_FILE_TYPE = Dict[
    str,
    Union[
        str,
        bool,
        MANIFEST_FILE_VPC_TYPE,
        List[MANIFEST_FILE_TEAM_TYPE],
        MANIFEST_FILE_IMAGES_TYPE,
    ],
]
MANIFEST_TYPE = Dict[
    str,
    Union[
        None,
        str,
        bool,
        MANIFEST_VPC_TYPE,
        List[MANIFEST_TEAM_TYPE],
    ],
]

MANIFEST_FILE_IMAGES_DEFAULTS: MANIFEST_FILE_IMAGES_TYPE = cast(
    MANIFEST_FILE_IMAGES_TYPE,
    {
        "jupyter-hub": {
            "repository": "aws-datamaker-jupyter-hub",
            "source": "dockerhub",
            "version": "latest",
        },
        "jupyter-user": {
            "repository": "aws-datamaker-jupyter-user",
            "source": "dockerhub",
            "version": "latest",
        },
        "landing-page": {
            "repository": "aws-datamaker-landing-page",
            "source": "dockerhub",
            "version": "latest",
        },
    },
)


class Manifest:
    def __init__(self, filename: str) -> None:
        self.filename: str = filename
        self.filename_dir: str = utils.path_from_filename(filename=filename)
        self.raw_file: MANIFEST_FILE_TYPE = self._read_manifest_file(filename=filename)
        self.name: str = cast(str, self.raw_file["name"])
        if "region" in self.raw_file:
            self.region: str = cast(str, self.raw_file["region"])
        else:
            self.region = utils.get_region()
        self.demo: bool = cast(bool, self.raw_file.get("demo", False))
        self.dev: bool = cast(bool, self.raw_file.get("dev", False))
        self.codeartifact_domain: Optional[str] = cast(Optional[str], self.raw_file.get("codeartifact-domain", None))
        self.codeartifact_repository: Optional[str] = cast(
            Optional[str], self.raw_file.get("codeartifact-repository", None)
        )
        self.images: MANIFEST_FILE_IMAGES_TYPE = cast(
            MANIFEST_FILE_IMAGES_TYPE, self.raw_file.get("images", MANIFEST_FILE_IMAGES_DEFAULTS)
        )
        self.env_tag: str = f"datamaker-{self.name}"
        self.ssm_parameter_name: str = f"/datamaker/{self.name}/manifest"
        self.ssm_dockerhub_parameter_name: str = f"/datamaker/{self.name}/dockerhub"
        self.toolkit_stack_name: str = f"datamaker-{self.name}-toolkit"
        self.cdk_toolkit_stack_name: str = f"datamaker-{self.name}-cdk-toolkit"
        self.demo_stack_name: str = f"datamaker-{self.name}-demo"
        self.env_stack_name: str = f"datamaker-{self.name}"
        self.eks_stack_name: str = f"eksctl-{self.env_stack_name}-cluster"
        self.toolkit_codebuild_project: str = f"datamaker-{self.name}"
        self.account_id: str = utils.get_account_id(manifest=self)
        self.available_eks_regions: List[str] = self._boto3_session().get_available_regions("eks")
        self.teams: List[TeamManifest] = self._parse_teams()
        self.vpc: VpcManifest = self._parse_vpc()

        self.cognito_external_provider: Optional[str] = cast(Optional[str], self.raw_file.get("external-idp", None))
        self.cognito_external_provider_label: Optional[str] = cast(
            Optional[str], self.raw_file.get("external-idp-label", None)
        )

        # Need to fill up

        self.deploy_id: Optional[str] = None  # toolkit
        self.toolkit_kms_arn: Optional[str] = None  # toolkit
        self.toolkit_kms_alias: Optional[str] = None  # toolkit
        self.toolkit_s3_bucket: Optional[str] = None  # toolkit
        self.cdk_toolkit_s3_bucket: Optional[str] = None  # toolkit

        self.raw_ssm: Optional[MANIFEST_TYPE] = None  # Env
        self.eks_cluster_role_arn: Optional[str] = None  # Env
        self.eks_env_nodegroup_role_arn: Optional[str] = None  # Env
        self.user_pool_client_id: Optional[str] = None  # Env
        self.identity_pool_id: Optional[str] = None  # Env
        self.user_pool_id: Optional[str] = None  # Env
        self.cognito_users_urls: Optional[str] = None  # Env

        self.landing_page_url: Optional[str] = None  # Kubectl

        self.cognito_external_provider_domain: Optional[str] = None  # Cognito
        self.cognito_external_provider_redirect: Optional[str] = None  # Cognito

    @staticmethod
    def _read_manifest_file(filename: str) -> MANIFEST_FILE_TYPE:
        _logger.debug("reading manifest file (%s)", filename)
        with open(filename, "r") as f:
            return cast(MANIFEST_FILE_TYPE, yaml.safe_load(f))

    @staticmethod
    def _botocore_config() -> botocore.config.Config:
        return botocore.config.Config(retries={"max_attempts": 5}, connect_timeout=10, max_pool_connections=10)

    @staticmethod
    def _parse_plugins(team: MANIFEST_FILE_TEAM_TYPE) -> List[PluginManifest]:
        if "plugins" in team:
            return [
                PluginManifest(name=p["name"], path=p["path"])
                for p in cast(List[MANIFEST_FILE_PLUGIN_TYPE], team["plugins"])
            ]
        return []

    def _parse_teams(self) -> List[TeamManifest]:
        return [
            TeamManifest(
                manifest=self,
                name=cast(str, t["name"]),
                instance_type=cast(str, t["instance-type"]),
                local_storage_size=cast(int, t["local-storage-size"]),
                nodes_num_desired=cast(int, t["nodes-num-desired"]),
                nodes_num_max=cast(int, t["nodes-num-max"]),
                nodes_num_min=cast(int, t["nodes-num-min"]),
                policy=cast(str, t["policy"]),
                grant_sudo=cast(bool, t["grant-sudo"]),
                image=cast(Optional[str], t.get("image")),
                plugins=self._parse_plugins(team=t),
            )
            for t in cast(List[MANIFEST_FILE_TEAM_TYPE], self.raw_file["teams"])
        ]

    def _parse_vpc(self) -> VpcManifest:
        raw_vpc = cast(Optional[MANIFEST_FILE_VPC_TYPE], self.raw_file.get("vpc", None))
        if raw_vpc is not None:
            subnets: List[SubnetManifest] = []
            if raw_vpc.get("private-subnets-ids"):
                for s in cast(List[MANIFEST_FILE_SUBNET_TYPE], raw_vpc.get("private-subnets-ids")):
                    subnets.append(SubnetManifest(manifest=self, subnet_id=s, kind=SubnetKind.private))
            if raw_vpc.get("public-subnets-ids"):
                for s in cast(List[MANIFEST_FILE_SUBNET_TYPE], raw_vpc.get("public-subnets-ids")):
                    subnets.append(SubnetManifest(manifest=self, subnet_id=s, kind=SubnetKind.public))
            if raw_vpc.get("isolated-subnets-ids"):
                for s in cast(List[MANIFEST_FILE_SUBNET_TYPE], raw_vpc.get("isolated-subnets-ids")):
                    subnets.append(SubnetManifest(manifest=self, subnet_id=s, kind=SubnetKind.isolated))
            return VpcManifest(
                manifest=self,
                subnets=subnets,
            )
        return VpcManifest(manifest=self, subnets=[])

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
            for team in self.teams:
                team.write_manifest_ssm()

    def _write_manifest_file(self) -> None:
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        with open(self.filename, "w") as file:
            yaml.safe_dump(data=self.asdict_file(), stream=file, sort_keys=False, indent=4)
        _logger.debug("Manifest file updated: %s", self.filename)

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
            self.deploy_id = cast(Optional[str], raw.get("deploy-id"))
            self.toolkit_s3_bucket = cast(Optional[str], raw.get("toolkit-s3-bucket"))
            self.toolkit_kms_alias = cast(Optional[str], raw.get("toolkit-kms-alias"))
            self.toolkit_kms_arn = cast(Optional[str], raw.get("toolkit-kms-arn"))
            self.cdk_toolkit_s3_bucket = cast(Optional[str], raw.get("cdk-toolkit-s3-bucket"))
            self.eks_cluster_role_arn = cast(Optional[str], raw.get("eks-cluster-role-arn"))
            self.eks_env_nodegroup_role_arn = cast(Optional[str], raw.get("eks-env-nodegroup-role-arn"))
            self.user_pool_client_id = cast(Optional[str], raw.get("user-pool-client-id"))
            self.identity_pool_id = cast(Optional[str], raw.get("identity-pool-id"))
            self.cognito_external_provider_domain = cast(Optional[str], raw.get("cognito-external-provider-domain"))
            self.cognito_external_provider_redirect = cast(Optional[str], raw.get("cognito-external-provider-redirect"))

            self.user_pool_id = cast(Optional[str], raw.get("user-pool-id"))
            if self.user_pool_id is not None:
                self.cognito_users_urls = cognito.get_users_url(user_pool_id=self.user_pool_id, region=self.region)

            self.vpc.fillup_from_ssm()
            for team in self.teams:
                team.fillup_from_ssm()

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
            if output["ExportName"] == f"datamaker-{self.name}-deploy-id":
                _logger.debug("Export value: %s", output["OutputValue"])
                self.deploy_id = output["OutputValue"]
            if output["ExportName"] == f"datamaker-{self.name}-kms-arn":
                _logger.debug("Export value: %s", output["OutputValue"])
                self.toolkit_kms_arn = output["OutputValue"]
        if self.deploy_id is None:
            raise RuntimeError(
                f"Stack {self.toolkit_stack_name} does not have the expected datamaker-{self.name}-deploy-id output."
            )
        if self.toolkit_kms_arn is None:
            raise RuntimeError(
                f"Stack {self.toolkit_stack_name} does not have the expected datamaker-{self.name}-kms-arn output."
            )
        self.toolkit_kms_alias = f"datamaker-{self.name}-{self.deploy_id}"
        self.toolkit_s3_bucket = f"datamaker-{self.name}-toolkit-{self.account_id}-{self.deploy_id}"
        self.cdk_toolkit_s3_bucket = f"datamaker-{self.name}-cdk-toolkit-{self.account_id}-{self.deploy_id}"
        for team in self.teams:
            team.scratch_bucket = f"datamaker-{self.name}-{team.name}-scratch-{self.account_id}-{self.deploy_id}"
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

        subnets: List[SubnetManifest] = []
        for output in response["Stacks"][0]["Outputs"]:
            if output["ExportName"] == f"datamaker-{self.name}-private-subnets-ids":
                for subnet_id in output["OutputValue"].split(","):
                    _logger.debug("Adding private subnet %s in the manifest.", subnet_id)
                    subnets.append(SubnetManifest(manifest=self, subnet_id=subnet_id, kind=SubnetKind.private))
            elif output["ExportName"] == f"datamaker-{self.name}-public-subnets-ids":
                for subnet_id in output["OutputValue"].split(","):
                    _logger.debug("Adding public subnet %s in the manifest.", subnet_id)
                    subnets.append(SubnetManifest(manifest=self, subnet_id=subnet_id, kind=SubnetKind.public))
            elif output["ExportName"] == f"datamaker-{self.name}-isolated-subnets-ids":
                for subnet_id in output["OutputValue"].split(","):
                    _logger.debug("Adding isolated subnet %s in the manifest.", subnet_id)
                    subnets.append(SubnetManifest(manifest=self, subnet_id=subnet_id, kind=SubnetKind.isolated))
        self.vpc.subnets = subnets
        self.fetch_ssm()
        self.write_manifest_ssm()
        self._write_manifest_file()
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
            self.fetch_demo_data()
            self.fetch_network_data()
            self.fetch_cognito_external_idp_data()

    def asdict_file(self) -> MANIFEST_FILE_TYPE:
        obj: MANIFEST_FILE_TYPE = {
            "name": self.name,
            "region": self.region,
        }
        if self.demo:
            obj["demo"] = True
        if self.dev:
            obj["dev"] = True
        if self.codeartifact_domain is not None:
            obj["codeartifact-domain"] = self.codeartifact_domain
        if self.codeartifact_repository is not None:
            obj["codeartifact-repository"] = self.codeartifact_repository
        if self.cognito_external_provider is not None:
            obj["external-idp"] = self.cognito_external_provider
        if self.cognito_external_provider_label is not None:
            obj["external-idp-label"] = self.cognito_external_provider_label

        obj["images"] = self.images
        obj["vpc"] = self.vpc.asdict_file()
        obj["teams"] = [t.asdict_file() for t in self.teams]
        return obj

    def asdict(self) -> MANIFEST_TYPE:
        obj: MANIFEST_TYPE = utils.replace_underscores(vars(self))
        obj["vpc"] = self.vpc.asdict()
        obj["teams"] = [t.asdict() for t in self.teams]
        del obj["filename"]
        del obj["filename-dir"]
        del obj["raw-ssm"]
        del obj["raw-file"]
        return obj

    def asjson(self) -> str:
        return str(json.dumps(obj=self.asdict(), sort_keys=True))

    def get_team_by_name(self, name: str) -> Optional[TeamManifest]:
        for t in self.teams:
            if t.name == name:
                return t
        return None
