import json
import logging
import os
from typing import Any, Dict, List, Optional

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context: Optional[Dict[str, Any]]) -> List[str]:
    ecs = boto3.client("ecs")
    if "compute" in event.keys():
        compute = event["compute"]
    else:
        compute = {}

    all_env_vars = [
        {"name": "task_type", "value": event["task_type"]},
        {"name": "tasks", "value": "{'tasks': " + str(event["tasks"]) + "}"},
        {"name": "compute", "value": "{'compute': " + str(compute) + "}"},
        {"name": "DATAMAKER_TEAM_SPACE", "value": os.environ["AWS_DATAMAKER_TEAMSPACE"]},
        {"name": "AWS_DATAMAKER_ENV", "value": os.environ["AWS_DATAMAKER_ENV"]},
        {"name": "JUPYTERHUB_USER", "value": event.get("JUPYTERHUB_USER", "")},
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
        platformVersion="1.4.0",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": json.loads(os.environ["SUBNETS"]),
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
                    "command": ["python", "/opt/python-utils/notebook_cli.py"],
                    "environment": all_env_vars,
                }
            ],
            "taskRoleArn": os.environ["ROLE"],
        },
    )

    return [response["tasks"][0]["taskArn"]]
