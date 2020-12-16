import json
import os
from os.path import expanduser
from typing import Dict, Tuple

import boto3
from yaml import safe_load

# Tags
DATAMAKER_PRODUCT_KEY = "Product"
DATAMAKER_SUBPRODUCT_KEY = "SubProduct"
DATAMAKER_SUBPRODUCT_EMR = "EMR"
DATAMAKER_PRODUCT_NAME = "DataMaker"
DATAMAKER_ENV = "Env"
DATAMAKER_TEAM_SPACE = "TeamSpace"


def get_properties() -> Dict[str, str]:
    """
    Returns the properties and pathnames of the current DataMaker Environment.

    Parameters
    ----------
    None
        None.

    Returns
    -------
    prop : dict
        Dictionary containing pathnames for the DataMaker Enviornment, Team Space, S3 Bucket Path, DataMaker Source
        Repository and ECS Cluster.

    Example
    -------
    >>> from datamaker_sdk.common import get_properties
    >>> props = get_properties()
    """
    if "AWS_DATAMAKER_ENV" in os.environ.keys():
        if (
            "DATAMAKER_TEAM_SPACE" not in os.environ.keys()
            or "AWS_DATAMAKER_S3_BUCKET" not in os.environ.keys()
        ):
            raise Exception(
                "if AWS_DATAMAKER_ENV then DATAMAKER_TEAM_SPACE, AWS_DATAMAKER_S3_BUCKET and "
                "must be set"
            )
        else:
            prop = dict(
                AWS_DATAMAKER_ENV=os.environ.get("AWS_DATAMAKER_ENV", ""),
                DATAMAKER_TEAM_SPACE=os.environ.get("DATAMAKER_TEAM_SPACE", ""),
                AWS_DATAMAKER_S3_BUCKET=os.environ.get("AWS_DATAMAKER_S3_BUCKET", ""),
            )
    else:
        # this path is used by the sagemaker notebooks where we cannot create the env variable in the context of the notebook
        home = expanduser("~")
        propFilePath = f"{home}/datamaker.yaml"
        with open(propFilePath, "r") as f:
            prop = safe_load(f)["properties"]

    prop[
        "ecs_cluster"
    ] = f"datamaker-{prop['AWS_DATAMAKER_ENV']}-{prop['DATAMAKER_TEAM_SPACE']}-cluster"
    prop["eks_cluster"] = f"datamaker-{prop['AWS_DATAMAKER_ENV']}"
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
    >>> from datamaker_sdk.common import split_s3_path
    >>> bucket, key = split_s3_path("s3://my-bucket/prefix/myobject.csv")
    """

    path_parts = s3_path.replace("s3://", "").split("/")
    bucket = path_parts.pop(0)
    key = "/".join(path_parts)
    return bucket, key


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
    >>> from datamaker_sdk.common import get_workspace
    >>> workspace = get_workspace()
    """
    ssm = boto3.client("ssm")
    props = get_properties()

    role_key = f"/datamaker/{props['AWS_DATAMAKER_ENV']}/teams/{props['DATAMAKER_TEAM_SPACE']}/manifest"

    role_config_str = ssm.get_parameter(Name=role_key)["Parameter"]["Value"]

    config = json.loads(role_config_str)
    my_session = boto3.session.Session()
    my_region = my_session.region_name
    config["region"] = my_region
    config["env_name"] = props["AWS_DATAMAKER_ENV"]
    config["team_space"] = props["DATAMAKER_TEAM_SPACE"]

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
    >>> from datamaker_sdk.common import get_scratch_database
    >>> scratch_database = get_scratch_database()
    """
    glue = boto3.client("glue")
    response = glue.get_databases()
    workspace = get_workspace()
    scratch_db_name = f"scratch_db_{workspace['env_name']}_{workspace['team_space']}".lower().replace("-", "_")
    new_location = f"s3://{workspace['scratch-bucket']}/{workspace['team_space']}/{scratch_db_name}"
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
                DATAMAKER_PRODUCT_KEY: DATAMAKER_PRODUCT_NAME,
                DATAMAKER_ENV: workspace["env_name"],
                DATAMAKER_TEAM_SPACE: workspace["team_space"],
            },
        }
    )
    return scratch_db_name
