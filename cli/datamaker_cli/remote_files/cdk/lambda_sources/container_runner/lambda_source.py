import json
import logging
import os
import sys
import time

import boto3
from datamaker.common.datamaker_constants import *

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    ecs = boto3.client("ecs")
    if "compute" in event.keys():
        compute = event["compute"]
    else:
        compute = {}

    all_env_vars = [
        {"name": "task_type", "value": event["task_type"]},
        {"name": "tasks", "value": "{'tasks': " + str(event["tasks"]) + "}"},
        {"name": "compute", "value": "{'compute': " + str(compute) + "}"},
        {"name": "repos_url", "value": os.environ["GIT_REPO_URL"]},
        {"name": "AWS_DATAMAKER_REPO", "value": os.environ["AWS_DATAMAKER_REPO"]},
        {"name": "AWS_DATAMAKER_S3_BUCKET", "value": os.environ["AWS_DATAMAKER_S3_BUCKET"]},
        {"name": "s3_output", "value": os.environ["S3_OUTPUT"]},
        {"name": "DATAMAKER_TEAM_SPACE", "value": os.environ[DATAMAKER_TEAM_SPACE]},
        {"name": "AWS_DATAMAKER_ENV", "value": os.environ[DATAMAKER_ENV]},
    ]
    if "env_vars" in event.keys():
        env_vars = event["env_vars"]
        for v in env_vars:
            all_env_vars.append(v)

    logger.info("ecs container env vars:\n %s", all_env_vars)

    response = ecs.run_task(
        cluster=os.environ["CLUSTER"],
        taskDefinition=os.environ["TASK_DEFINITION"],
        count=1,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [
                    os.environ["SUBNET"],
                ],
                "securityGroups": [
                    os.environ["SECURITY_GROUP"],
                ],
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "datamaker-runner",
                    "command": ["python", "/root/notebook_cli.py"],
                    "environment": all_env_vars,
                }
            ],
            "taskRoleArn": os.environ["ROLE"],
        },
    )

    return [response["tasks"][0]["taskArn"]]
