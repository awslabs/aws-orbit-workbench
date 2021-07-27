import json
import logging
import os
from os.path import expanduser
from typing import Any, Dict, Tuple

import boto3
import botocore
from yaml import safe_load

from aws_orbit_sdk import __version__

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Tags
ORBIT_PRODUCT_KEY = "Product"
ORBIT_SUBPRODUCT_KEY = "SubProduct"
ORBIT_SUBPRODUCT_EMR = "EMR"
ORBIT_SUBPRODUCT_REDSHIFT = "Redshift"
ORBIT_PRODUCT_NAME = "Orbit Workbench"
ORBIT_ENV = "Env"
AWS_ORBIT_TEAM_SPACE = "TeamSpace"


def get_properties() -> Dict[str, str]:
    """
    Returns the properties and pathnames of the current Orbit Workbench Environment.

    Parameters
    ----------
    None
        None.

    Returns
    -------
    prop : dict
        Dictionary containing pathnames for the Orbit Workbench Enviornment, Team Space, S3 Bucket Path, Orbit Workbench Source
        Repository.

    Example
    -------
    >>> from aws_orbit_sdk.common import get_properties
    >>> props = get_properties()
    """
    if "AWS_ORBIT_ENV" in os.environ.keys():
        if "AWS_ORBIT_TEAM_SPACE" not in os.environ.keys():
            logger.error("current env vars: %s", os.environ.keys())
            raise Exception("if AWS_ORBIT_ENV then AWS_ORBIT_TEAM_SPACE must be set")
        else:
            prop = dict(
                AWS_ORBIT_ENV=os.environ.get("AWS_ORBIT_ENV", ""),
                AWS_ORBIT_TEAM_SPACE=os.environ.get("AWS_ORBIT_TEAM_SPACE", ""),
            )
            if "AWS_ORBIT_S3_BUCKET" in os.environ.keys():
                prop["AWS_ORBIT_S3_BUCKET"] = os.environ.get("AWS_ORBIT_S3_BUCKET")
    else:
        # this path is used by the sagemaker notebooks where we cannot create the env variable in the context of the notebook
        home = expanduser("~")
        propFilePath = f"{home}/orbit.yaml"
        with open(propFilePath, "r") as f:
            prop = safe_load(f)["properties"]

    prop["ecs_cluster"] = f"orbit-{prop['AWS_ORBIT_ENV']}-{prop['AWS_ORBIT_TEAM_SPACE']}-cluster"
    prop["eks_cluster"] = f"orbit-{prop['AWS_ORBIT_ENV']}"
    return prop


def split_s3_path(s3_path: str) -> Tuple[str, str]:
    """
    Splits a s3 bucket path to its bucket name and its key with prefixes.

    Parameters
    ----------
    s3_path : str
        s3 bucket path to split.

    Returns
    -------
    bucket : str
        Bucket name derived from the s3 path
    key : str
        Object key and prefixes in the s3 bucket

    Example
    -------
    >>> from aws_orbit_sdk.common import split_s3_path
    >>> bucket, key = split_s3_path("s3://my-bucket/prefix/myobject.csv")
    """

    path_parts = s3_path.replace("s3://", "").split("/")
    bucket = path_parts.pop(0)
    key = "/".join(path_parts)
    return bucket, key


def get_botocore_config() -> botocore.config.Config:
    return botocore.config.Config(
        retries={"max_attempts": 5},
        connect_timeout=10,
        max_pool_connections=10,
        user_agent_extra=f"awsorbit/{__version__}",
    )


def boto3_client(service_name: str) -> boto3.client:
    return boto3.Session().client(service_name=service_name, config=get_botocore_config())


def get_workspace() -> Dict[str, str]:
    """
    Returns workspace configuration for your given role for your Team Space in a dictionary object.

    Parameters
    ----------
    None
        None.

    Returns
    -------
    config : dict
        Dictionary object containing workspace config. on scratch-bucket, notebook_bucket, role_arn,
        instance_profile_arn, instance_profile_name, region, env_name, and team-space.

    Example
    -------
    >>> from aws_orbit_sdk.common import get_workspace
    >>> workspace = get_workspace()
    """
    ssm = boto3_client("ssm")
    props = get_properties()

    role_key = f"/orbit/{props['AWS_ORBIT_ENV']}/teams/{props['AWS_ORBIT_TEAM_SPACE']}/context"

    role_config_str = ssm.get_parameter(Name=role_key)["Parameter"]["Value"]

    config = json.loads(role_config_str)
    my_session = boto3.session.Session()
    my_region = my_session.region_name
    config["region"] = my_region
    config["env_name"] = props["AWS_ORBIT_ENV"]
    config["team_space"] = props["AWS_ORBIT_TEAM_SPACE"]
    config["ScratchBucket"] = f"s3://{config['ScratchBucket']}/{props['AWS_ORBIT_TEAM_SPACE']}"

    return config


def get_scratch_database() -> str:
    """
    Creates a new scratch database for the TeamSpace located in the scratch s3 bucket.

    Parameters
    ----------
    None
        None.

    Returns
    -------
    scratch_db_name : str
        Name of the new scratch database

    Example
    -------
    >>> from aws_orbit_sdk.common import get_scratch_database
    >>> scratch_database = get_scratch_database()
    """
    glue = boto3.client("glue")
    response = glue.get_databases()
    workspace = get_workspace()
    scratch_db_name = f"scratch_db_{workspace['env_name']}_{workspace['team_space']}".lower().replace("-", "_")
    new_location = f"{workspace['ScratchBucket']}/{scratch_db_name}"
    for db in response["DatabaseList"]:
        if db["Name"].lower() == scratch_db_name:
            if new_location == db["LocationUri"]:
                return scratch_db_name
            else:
                ## scratch database left from previous teamspace creation , will delete it.
                glue.delete_database(Name=scratch_db_name)

    response = glue.create_database(
        DatabaseInput={
            "Name": scratch_db_name,
            "Description": f"scratch database for TeamSpace {workspace['env_name']}.{workspace['team_space']}",
            "LocationUri": new_location,
            "Parameters": {
                ORBIT_PRODUCT_KEY: ORBIT_PRODUCT_NAME,
                ORBIT_ENV: workspace["env_name"],
                AWS_ORBIT_TEAM_SPACE: workspace["team_space"],
            },
        }
    )
    return scratch_db_name


def get_stepfunctions_waiter_config(delay: int, max_attempts: int) -> Dict[str, Any]:
    return {
        "version": 2,
        "waiters": {
            "ExecutionComplete": {
                "operation": "DescribeExecution",
                "delay": delay,
                "maxAttempts": max_attempts,
                "acceptors": [
                    {
                        "matcher": "path",
                        "expected": "SUCCEEDED",
                        "argument": "status",
                        "state": "success",
                    },
                    {
                        "matcher": "path",
                        "expected": "RUNNING",
                        "argument": "status",
                        "state": "retry",
                    },
                    {
                        "matcher": "path",
                        "expected": "FAILED",
                        "argument": "status",
                        "state": "failure",
                    },
                    {
                        "matcher": "path",
                        "expected": "TIMED_OUT",
                        "argument": "status",
                        "state": "failure",
                    },
                    {
                        "matcher": "path",
                        "expected": "ABORTED",
                        "argument": "status",
                        "state": "failure",
                    },
                ],
            },
        },
    }
