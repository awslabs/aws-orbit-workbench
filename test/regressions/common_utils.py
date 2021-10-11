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



import os
from typing import Any, Dict
import pytest

from aws_orbit_sdk.common import get_workspace
import boto3
import json
from pathlib import Path

import logging
# Initialize parameters
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger()


JOB_COMPLETION_STATUS = "Complete"
JOB_FAILED_STATUS = "Failed"


workspace = get_workspace()

S3 = boto3.client('s3')
GLUE = boto3.client('glue')


def get_ssm_parameters(ssm_string, ignore_not_found=False):
    ssm = boto3.client('ssm')
    try:
        return json.loads(ssm.get_parameter(Name=ssm_string)['Parameter']['Value'])
    except Exception as e:
        if ignore_not_found:
            return {}
        else:
            raise e


def get_demo_configuration(env_name):
    return get_ssm_parameters(f"/orbit/{env_name}/demo", True)


def create_db(name, location, description=''):
    try:
        response = GLUE.delete_database(
            Name=name
        )
    except Exception as e:
        logger.error(e)
        pass
    response = GLUE.create_database(
        DatabaseInput={
            'Name': name,
            'Description': description,
            'LocationUri': f's3://{location}/{name}'
        }
    )

def get_schemas(source_bucket_name, prefix='', suffix=''):
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(name=source_bucket_name)
    schemas = []
    for o in bucket.objects.all():
        if (o.key.startswith(prefix)):
            name = os.path.basename(o.key).split(".")[0]
            schemaStr = o.get()['Body'].read().decode('utf-8')
            schema = json.loads(schemaStr)  # StructType.fromJson(json.loads(schemaStr))
            schemas.append((name, schema))
    return schemas

def get_schema(schemas, filename):
    for (schema_name, schema) in schemas:
        # logger.info(f"{schema_name} in {filename} : {schema_name in filename}")
        if schema_name in filename:
            return schema_name, schema
    return None, None

def clean_bucket_prefix(bucket_name, prefix) -> None:
    response = S3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    if "Contents" in response:
        for object in response["Contents"]:
            logger.info("Deleting {object['Key']}")
            S3.delete_object(Bucket=bucket_name, Key=object["Key"])


def check_database_exists(database_name) -> str:
    response = GLUE.get_database(Name=database_name)
    return response.get('Database').get("Name")


def get_s3_extracted_files(bucket_name, source_folder):   
    # returning a list
    s3_files= []
    s3_files_response = S3.list_objects_v2(Bucket=bucket_name, Prefix=source_folder)
    if 'Contents' in s3_files_response:
        s3_files = s3_files_response['Contents']
    logger.info(f"s3_files={s3_files}")
    return s3_files