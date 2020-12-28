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
import time
import urllib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import boto3
import pandas as pd

from datamaker_sdk.common import get_properties

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()


def get_execution_history(notebookDir: str, notebookName: str) -> pd.DataFrame:
    """
     Get Notebook Execution History

     Parameters
     ----------
     notebookDir: str
         Name of notebook directory.
     notebookName: str
         Name of notebook.

     Returns
     -------
     df: pd.DataFrame
         Notebook execution history.

     Example
     --------
    >>> from aws_orbit_sdk import controller
    >>> controller.get_execution_history(notebookDir="notebook-directory", notebookName='mynotebook')
    """
    props = get_properties()
    return _get_execution_history_from_local(notebookDir, notebookName, props)


def _get_execution_history_from_local(
    notebook_basedir: str, src_notebook: str, props: dict
) -> pd.DataFrame:
    """
    Get Notebook Execution History from EFS
    """

    home = str(Path.home())
    nb_name = Path(src_notebook).stem
    notebook_dir = os.path.join(home, notebook_basedir, nb_name)

    executions = []
    for nb in Path(notebook_dir).glob("*.ipynb"):
        if not nb.is_file():
            continue
        executions.append(
            (str(nb), datetime.fromtimestamp(nb.stat().st_mtime), notebook_dir)
        )

    if not executions:
        print(f"No output notebooks founds at: {notebook_dir}")

    df = pd.DataFrame(executions, columns=["relativePath", "timestamp", "path"])
    return df


def _get_execution_history_from_s3(
    notebookBaseDir: str, srcNotebook: str, props: str
) -> pd.DataFrame:
    """
    Get Notebook Execution History from s3
    """
    s3 = boto3.client("s3")

    notebookDir = os.path.join(notebookBaseDir, srcNotebook.split(".")[0])

    path = "{}/output/notebooks/{}/".format(props["DATAMAKER_TEAM_SPACE"], notebookDir)
    executions = []
    objects = s3.list_objects_v2(Bucket=props["AWS_DATAMAKER_S3_BUCKET"], Prefix=path)
    if "Contents" in objects.keys():
        for key in s3.list_objects_v2(
            Bucket=props["AWS_DATAMAKER_S3_BUCKET"], Prefix=path
        )["Contents"]:
            if key["Key"][-1] == "/":
                continue
            notebookName = os.path.basename(key["Key"])
            path = key["Key"]
            arg = urllib.parse.quote(path)
            s3path = "s3://{}/{}".format(props["AWS_DATAMAKER_S3_BUCKET"], path)
            #     link = '<a href="{}" target="_blank">{}</a>'.format(site + arg,"open")
            timestamp = key["LastModified"]
            executions.append((notebookName, timestamp, s3path))
    else:
        print(
            "No output notebooks founds at: s3://{}/{}".format(
                props["AWS_DATAMAKER_S3_BUCKET"], path
            )
        )

    df = pd.DataFrame(executions, columns=["relativePath", "timestamp", "s3path"])
    return df


def _get_invoke_function_name() -> Any:
    """
    Get invoke function Name.

    Returns
    -------
    Function Name.
    """
    props = get_properties()
    functionName = f"datamaker-{props['AWS_DATAMAKER_ENV']}-{props['DATAMAKER_TEAM_SPACE']}-container-runner"
    return functionName


def run_python(taskConfiguration: dict) -> Any:
    """
    Runs Python Task

    Parameters
    ----------
    taskConfiguration : dict
        A task definition to execute.

        tasks : lst
            A list of python task definition to run.
        module : str
           The python module to run (without .py ext).
        functionName : str
                The python function to start the execution.
        sourcePaths : lst
              A list of s3 python source paths used for importing packages or modules into the application.
        params : dict
             A list of parameters for this task to override the notebook parameters.
        compute : optional, dict
              A list of runtime parameters to control execution.
        container : dict
               A list of parameters to control container execution.
        p_concurrent : str
              The number of parallel threads inside the container that will execute notebooks.
        env_vars : optional, list
              A list of environment parameters to pass to the container.

    Returns
    -------
    response: Any
        Response for the function or an error object.

    Example
    --------
    >>> import aws_orbit_sdk.controller as controller
    >>> response = controller.run_python(
    ...     taskConfiguration = {
    ...         "tasks":  [
    ...             {
    ...                 "module": "pyspark.run_pyspark_local",
    ...                 "functionName": "run_spark_job",
    ...                 "sourcePaths": ["DataScienceRepo/samples/python"],
    ...                  "params": {
    ...                            "bucket": "users-env2",
    ...                          "p2": 'bar'
    ...                  }
    ...              }
    ...          ],
    ...          "compute": {
    ...             "container" : {
    ...                 "p_concurrent": "4"
    ...          },
    ...           "env_vars": [
    ...                      {
    ...                         'name': 'cluster_name',
    ...                          'value': clusterName
    ...                      }
    ...          ]
    ...      })
    """
    taskConfiguration["task_type"] = "python"
    return _run_task(taskConfiguration)


def run_notebooks(taskConfiguration: dict) -> Any:
    """
    Runs Notebooks Tasks

    Parameters
    ----------
    taskConfiguration : dict
        A task definition to execute.
        notebooks : lst
            A list of notebook task definition to run.
        notebookName : str
            The filename of the notebook.
        notebookName : str
            The relative path to the notebook file starting at the repository root.
        targetPath : str
             The target S3 directory where the output notebook and all related output will be generated.
        params : dict
             A list of parameters for this task to override the notebook parameters.
        compute : optional, dict
              A list of runtime parameters to control execution.
        container : dict
               A list of parameters to control container execution.
        p_concurrent : str
              The number of parallel processes inside the container that will execute notebooks.
        sns.topic.name : str
              A name of a topic to which messages are sent on task completion or failure.
        env_vars : optional, lst
             A list of environment parameters to pass to the container.

    Returns
    -------
    response: Any
        Response for the function or an error object.

    Example
    --------
    >>> import aws_orbit_sdk.controller as controller
    >>> response = controller.run_notebooks(
    ...     taskConfiguration = {
    ...         "notebooks":  [ {
    ...           "notebookName": "Example-2-Extract-Files.ipynb",
    ...           "sourcePath": "samples/notebooks/A-LakeCreator",
    ...           "targetPath": "tests/createLake",
    ...           "params": {
    ...             "bucketName": bucketName,
    ...             "zipFileName": file,
    ...             "targetFolder": extractedFolder
    ...           },
    ...           ...
    ...         },
    ...         "compute": {
    ...             "container" : {
    ...                 "p_concurrent": "4",
    ...             },
    ...             "env_vars": [
    ...                         {
    ...                             'name': 'cluster_name',
    ...                             'value': clusterName
    ...                         }
    ...             ],
    ...             "sns.topic.name": 'TestTopic',
    ...         }
    ... )
    """
    taskConfiguration["task_type"] = "jupyter"
    return _run_task(taskConfiguration)


def _run_task(taskConfiguration: dict) -> Any:
    """
    Runs Task in Python in a notebook using lambda.

    Parameters
    ----------
    taskConfiguration: dict
        A task definition to execute.

    Returns
    -------
    Response Payload
    """
    lambda_client = boto3.client("lambda")
    taskConfiguration["jupyterhub_user"] = os.environ.get("JUPYTERHUB_USER", None)
    payload = json.dumps(taskConfiguration)
    logger.debug(payload)
    response = lambda_client.invoke(
        FunctionName=_get_invoke_function_name(),
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=bytes(payload, "utf-8"),
    )
    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        response_payload = json.loads(response["Payload"].read().decode("utf-8"))
    else:
        response_payload = None

    return response_payload


def schedule_python(
    triggerName: str, frequency: str, taskConfiguration: Dict[str, Any]
) -> str:
    """
    Schedule Python Task

    Parameters
    -----------
    triggerName: str
      A unique name of the time trigger that will start this execution.
    frequency: str
       A cron string e.g., cron(0/15 * 1/1 * ? *) to define the starting times of the execution.
    taskConfiguration: dict
         A task definition to execute

        tasks: lst
            A list of python task definition to run.
        module : str
           The python module to run (without .py ext).
        functionName : str
                The python function to start the execution.
        sourcePaths : lst
              A list of s3 python source paths used for importing packages or modules into the application.
        params : dict
             A list of parameters for this task to override the notebook parameters.
        compute : optional, dict
              A list of runtime parameters to control execution.
        container : dict
               A list of parameters to control container execution.
        p_concurrent : str
               The number of parallel threads inside the container that will execute notebooks.
        env_vars : optional, list
              A list of environment parameters to pass to the container.

    Returns
    --------
    arn : str
        The response will be ARN of the event rule created to start this execution:'arn:aws:events:us-east-2:...'

    Example
    --------
    Schedule python task similar to 'run_python' task config. example (refer to 'run_python').
    """
    taskConfiguration["task_type"] = "python"
    return schedule_task(triggerName, frequency, taskConfiguration)


def schedule_notebooks(
    triggerName: str, frequency: str, taskConfiguration: dict
) -> str:
    """
    Schedules Notebooks
    Parameters
    ---------
    triggerName: str
        A unique name of the time trigger that will start this exec
    frequency: str
        A cron string e.g., cron(0/15 * 1/1 * ? *) to define the starting times of the execution
    taskConfiguration: dict
        A task definition to execute

        notebooks : lst
            A list of notebook task definition to run.
        notebookName : str
            The filename of the notebook.
        notebookName : str
            The relative path to the notebook file starting at the repository root.
        targetPath : str
            The target S3 directory where the output notebook and all related output will be generated.
        params : dict
            A list of parameters for this task to override the notebook parameters.
        compute : optional, dict
            A list of runtime parameters to control execution.
        container : dict
            A list of parameters to control container execution.
        p_concurrent : str
            The number of parallel threads inside the container that will execute notebooks.
        env_vars : optional, list
            A list of environment parameters to pass to the container.

    Returns
    -------
    arn: str
        The response will be ARN of the event rule created to start this execution: 'arn:aws:events:us-east-2:...'

    Example
    --------
    Schedule python task similar to 'run_notebook' task config. example (refer to 'run_notebook').
    """
    taskConfiguration["task_type"] = "jupyter"
    return schedule_task(triggerName, frequency, taskConfiguration)


def schedule_task(triggerName: str, frequency: str, notebookConfiguration: dict) -> Any:
    """
    Parameters
    ----------
    triggerName: str
        A unique name of the time trigger that will start this exec
    frequency: str
        A cron string e.g., cron(0/15 * 1/1 * ? *) to define the starting times of the execution
    notebookConfiguration: Any

    Return
    ------
    arn : str
        The response will be ARN of the event rule created to start this execution:'arn:aws:events:us-east-2:...'

    Example
    -------
    Example for schedule_task similar to run_python and run_notebook tasks (refer to 'run_python').
    """
    lambda_client = boto3.client("lambda")
    events_client = boto3.client("events")
    fn_response = lambda_client.get_function(FunctionName=_get_invoke_function_name())

    fn_arn = fn_response["Configuration"]["FunctionArn"]

    try:
        events_client.delete_rule(Name=triggerName)
    except:
        print("Rule created first time")
    else:
        print("Deleted previous rule " + triggerName)

    rule_response = events_client.put_rule(
        Name=triggerName,
        ScheduleExpression=frequency.strip(),
        State="ENABLED",
    )

    target_response = events_client.put_targets(
        Rule=triggerName,
        Targets=[
            {"Id": "1", "Arn": fn_arn, "Input": json.dumps(notebookConfiguration)},
        ],
    )

    return rule_response["RuleArn"]


def delete_task_schedule(triggerName: str) -> None:
    """
    Delete Task Schedule

    Parameters
    ----------
    triggerName: str
        The arn of the event rule

    Returns
    -------
    None
        None.

    Example
    --------
    >>> import aws_orbit_sdk.controller as controller
    >>> controller.delete_scheduled_task(triggerName = 'arn:aws:events:...')
    """
    events_client = boto3.client("events")
    response = events_client.remove_targets(Rule=triggerName, Ids=["1"], Force=True)

    events_client.delete_rule(Name=triggerName, Force=True)
    print("notebook schedule deleted: ", triggerName)


def get_active_tasks(user_filter: Optional[Any]) -> Union[dict, List[Dict[str, Any]]]:
    """
    Get Active Tasks

    Parameters
    -----------
    user_filter: Any

    returns
    -------
    taskdef: dict
        Describes a list of Active Task Definitions

    Example
    --------
    >>> import aws_orbit_sdk.controller as controller
    >>> controller.get_active_tasks()
    """
    ecs = boto3.client("ecs")
    props = get_properties()
    clusterName = props["ecs_cluster"]

    task_definitions = []
    tasks = ecs.list_tasks(
        cluster=clusterName,
    )["taskArns"]

    if len(tasks) == 0:
        return {}
    task_descs = ecs.describe_tasks(cluster=clusterName, tasks=tasks)["tasks"]
    for t in task_descs:
        task_definition = {}
        task_definition["lastStatus"] = t["lastStatus"]
        #         task_definition['container'] = t
        vars = {}

        for k in t["overrides"]["containerOverrides"][0]["environment"]:
            vars[k["name"]] = k["value"]
        datamaker_task = json.loads(vars["tasks"].replace("'", '"'))
        if "notebookName" in datamaker_task["tasks"][0]:
            task_name = (
                datamaker_task["tasks"][0]["notebookName"].split(".")[0]
                if "notebookName" in datamaker_task["tasks"][0]
                else ""
            )
        elif "module" in datamaker_task["tasks"][0]:
            module = datamaker_task["tasks"][0]["module"]
            functionName = (
                datamaker_task["tasks"][0]["functionName"]
                if "functionName" in datamaker_task["tasks"][0]
                else ""
            )
            task_name = f"{module}.{functionName}"
        else:
            task_name = "unknown"

        task_definition["task_name"] = task_name
        task_definition["taskArn"] = t["taskArn"]
        task_definition["taskID"] = t["taskArn"]

        if "startedAt" in t:
            start_at = t["startedAt"]
            task_definition["epoch"] = start_at.timestamp()
            start_time = start_at.strftime("%Y-%m-%d %H:%M:%S")
            task_definition["start_time"] = start_time
            if "stoppedAt" in t:
                duration = t["stoppedAt"] - start_at
                task_definition["stop_time"] = t["stoppedAt"]
            else:
                now = datetime.now()
                start_at = start_at.replace(tzinfo=None)
                duration = now - start_at

            task_definition["duration"] = str(duration).split(".")[0]

        task_definitions.append(task_definition)

    task_definitions.sort(key=order_def)
    return task_definitions


def order_def(task_definition: Any) -> datetime:
    """
    Order task definitions by their timestamps of when they start at.

    Parameters
    -----------
    task_definition: Any

    Returns
    --------
    date : datetime
        Timestamp for a specific task definition, or the current timestamp if one does not already exist.
    """

    if "epoch" in task_definition:
        return task_definition["epoch"]
    return datetime.now().timestamp()


def wait_for_tasks_to_complete(
    tasks: List[Dict[str, str]],
    delay: Optional[int] = 60,
    maxAttempts: Optional[str] = 10,
    tail_log: Optional[bool] = False,
) -> None:
    """
    Parameters
    ----------
    tasks: lst
       A list of structures with container type, execution arn, and job arn.
    delay: int
       Number of seconds to wait until checking containers state again (default = 60).
    maxAttempts: str
        Number of attempts to check if containers stopped before returning a failure (default = 10).
    tail_log: bool
       if True, will tail the log of the containers until they are stopped (default = false).

    Returns
    -------
    None
        None.

    Example
    --------
    >>> from aws_orbit_sdk.controller import wait_for_tasks_to_complete


    """
    ecs = boto3.client("ecs")
    logs = boto3.client("logs")
    paginator = logs.get_paginator("filter_log_events")

    props = get_properties()
    clusterName = props["ecs_cluster"]

    ecs_tasks = [t["JobArn"] for t in tasks if t["ExecutionType"] == "ecs"]
    if not tail_log:
        waiter = ecs.get_waiter("tasks_stopped")
        waiter.wait(
            cluster=clusterName,
            tasks=ecs_tasks,
            WaiterConfig={"Delay": delay, "MaxAttempts": maxAttempts},
        )
    else:
        logGroupName = f"/datamaker/tasks/{props['AWS_DATAMAKER_ENV']}/{props['DATAMAKER_TEAM_SPACE']}/containers"
        logger.info("start logging from %s", logGroupName)
        logStreams = []
        for t in ecs_tasks:
            id = t.split("/")[2]
            logStreams.append(
                f"datamaker-{props['AWS_DATAMAKER_ENV']}-{props['DATAMAKER_TEAM_SPACE']}/datamaker-runner/{id}"
            )

        logger.info("waiting until tasks start running")

        try:
            ecs.get_waiter("tasks_running").wait(
                cluster=clusterName,
                tasks=ecs_tasks,
                WaiterConfig={"Delay": delay, "MaxAttempts": maxAttempts},
            )
            logger.info("Tasks started running...")
        except:
            logger.info("tasks already been terminated")

        remainingDelay = delay
        lastTime = 0
        try:
            while True:
                lastTime = logEvents(paginator, logGroupName, logStreams, lastTime)
                tasks_state = ecs.describe_tasks(cluster=clusterName, tasks=ecs_tasks)

                if all_tasks_stopped(tasks_state):
                    logger.info("All tasks stopped")
                    return

                if remainingDelay < 0:
                    maxAttempts -= 1
                    remainingDelay = delay
                if maxAttempts < 0:
                    logger.info("Stopped waiting as maxAttempts reached")
                    return
                throttle = 10
                time.sleep(throttle)
                remainingDelay -= throttle
        except Exception as ex:
            logger.error(ex)
            logger.error("Error logging from %s.%s", logGroupName, ",".join(logStreams))


def logEvents(paginator: Any, logGroupName: Any, logStreams: Any, fromTime: Any) -> int:
    """
    Parameters
    ----------
    paginator: Any
    logGroupName: Any
    logStreams: Any
    fromTime: Any

    Return
    -------

    Example
    -------
    """
    logging.basicConfig(
        format="%(message)s", level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S"
    )
    event_logger = logging.getLogger("event")

    response_iterator = paginator.paginate(
        logGroupName=logGroupName,
        logStreamNames=logStreams,
        interleaved=True,
        startTime=fromTime,
        PaginationConfig={"MaxItems": 10, "PageSize": 10},
    )
    lastTime = 0
    while True:
        for page in response_iterator:
            for e in page["events"]:
                t = datetime.fromtimestamp(e["timestamp"] / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                m = e["message"]
                print(t, m)
                lastTime = e["timestamp"]

            if "nextToken" in page.keys():
                marker = page["nextToken"]
            else:
                marker = None

        if marker == None:
            return lastTime + 1
        else:
            response_iterator = paginator.paginate(
                logGroupName=logGroupName,
                logStreamNames=logStreams,
                interleaved=True,
                PaginationConfig={
                    "MaxItems": 500,
                    "PageSize": 100,
                    "StartingToken": marker,
                },
            )


def all_tasks_stopped(tasks_state: Any) -> bool:
    """
    Checks if all tasks are stopped or if any are still running.

    Parameters
    ---------
    tasks_state: Any
        Task state dictionary object

    Returns
    --------
    response:  bool
        True if all tasks are stopped.

    """
    for t in tasks_state["tasks"]:
        if t["lastStatus"] in ("PENDING", "RUNNING"):
            return False
    return True
