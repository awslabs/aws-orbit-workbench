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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import boto3
import botocore
import pandas as pd
import yaml
from kubernetes import config as k8_config
from kubernetes import dynamic
from kubernetes import watch as k8_watch
from kubernetes.client import (
    ApiException,
    CoreV1Api,
    CustomObjectsApi,
    StorageV1Api,
    V1ContainerState,
    V1ContainerStatus,
    V1Pod,
    V1PodCondition,
    V1PodList,
    V1PodStatus,
    api_client,
    exceptions,
)

from aws_orbit_sdk.common import get_properties

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
_logger = logging.getLogger()

MANIFEST_PLUGIN_TYPE = Dict[str, Union[str, Dict[str, Any]]]
MANIFEST_PROPERTY_MAP_TYPE = Dict[str, Union[str, Dict[str, Any]]]
MANIFEST_FILE_TEAM_TYPE = Dict[str, Union[str, int, None, List[MANIFEST_PROPERTY_MAP_TYPE], List[str]]]
MANIFEST_TEAM_TYPE = Optional[Dict[str, Union[str, int, None, List[MANIFEST_PLUGIN_TYPE]]]]


__CURRENT_TEAM_MANIFEST__: MANIFEST_TEAM_TYPE = None
__CURRENT_ENV_MANIFEST__: MANIFEST_TEAM_TYPE = None

APP_LABEL_SELECTOR: List[str] = ["orbit-runner", "emr-spark"]

ORBIT_API_VERSION = "v1"
ORBIT_API_GROUP = "orbit.aws"


def read_team_manifest_ssm(env_name: str, team_name: str) -> Optional[MANIFEST_TEAM_TYPE]:
    parameter_name: str = f"/orbit/{env_name}/teams/{team_name}/manifest"
    _logger.debug("Trying to read manifest from SSM parameter (%s).", parameter_name)
    client = boto3.client("ssm")
    try:
        json_str: str = client.get_parameter(Name=parameter_name)["Parameter"]["Value"]
    except client.exceptions.ParameterNotFound:
        _logger.debug("Team %s Manifest SSM parameter not found: %s", team_name, parameter_name)
        return None
    _logger.debug("Team %s Manifest SSM parameter found.", team_name)
    return cast(MANIFEST_TEAM_TYPE, json.loads(json_str))


def get_parameter(client, name: str) -> Dict[str, Any]:
    try:
        json_str: str = client.get_parameter(Name=name)["Parameter"]["Value"]
    except botocore.errorfactory.ParameterNotFound:
        _logger.error("failed to read parameter %s", name)
        raise
    return cast(Dict[str, Any], json.loads(json_str))


def load_env_context_from_ssm(env_name: str) -> Optional[MANIFEST_TEAM_TYPE]:
    ssm = boto3.client("ssm")
    context_parameter_name: str = f"/orbit/{env_name}/context"
    context = get_parameter(ssm, name=context_parameter_name)
    return cast(MANIFEST_TEAM_TYPE, context)


def load_team_context_from_ssm(env_name: str, team_name: str) -> Optional[MANIFEST_TEAM_TYPE]:
    ssm = boto3.client("ssm")
    context_parameter_name: str = f"/orbit/{env_name}/teams/{team_name}/context"
    context = get_parameter(ssm, name=context_parameter_name)
    return cast(MANIFEST_TEAM_TYPE, context)


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


def _get_execution_history_from_local(notebook_basedir: str, src_notebook: str, props: dict) -> pd.DataFrame:
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
        executions.append((str(nb), datetime.fromtimestamp(nb.stat().st_mtime), notebook_dir))

    if not executions:
        _logger.info(f"No output notebooks founds at: {notebook_dir}")

    df = pd.DataFrame(executions, columns=["relativePath", "timestamp", "path"])
    return df


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
    if "compute_type" not in taskConfiguration or taskConfiguration["compute_type"] == "eks":
        return _run_task_eks(taskConfiguration)
    else:
        raise RuntimeError("Unsupported compute_type '%s'", taskConfiguration["compute_type"])


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
    ...         "tasks":  [ {
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
    if "compute_type" not in taskConfiguration or taskConfiguration["compute_type"] == "eks":
        return _run_task_eks(taskConfiguration)
    else:
        raise RuntimeError("Unsupported compute_type '%s'", taskConfiguration["compute_type"])


def list_team_running_jobs():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    return list_running_jobs(team_name)


def list_my_running_jobs():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    return list_running_jobs(namespace)


def list_running_jobs(namespace: str):
    api = _dynamic_client().resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    label_selector = "k8sJobType=Job"
    try:
        api_response = api.get(namespace=namespace, label_selector=label_selector)
        res = api_response.to_dict()
    except ApiException as e:
        _logger.info("Exception when calling DynamicClient.get() for OrbitJobs: %s\n" % e)
        raise e

    return [
        oj
        for oj in res.get("items", [])
        if oj.get("status", {}).get("orbitJobOperator", {}).get("jobStatus") == "Active"
    ]


def list_team_running_pods():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    return list_running_pods(team_name)


def list_my_running_pods():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    return list_running_pods(namespace)


def list_running_pods(namespace: str):
    load_kube_config()
    api_instance = CoreV1Api()

    app_list = ",".join(APP_LABEL_SELECTOR)
    label_selector = f"app in ({app_list})"
    _logger.debug("using job selector %s", label_selector)
    try:
        api_response = api_instance.list_namespaced_pod(
            namespace=namespace,
            _preload_content=False,
            label_selector=label_selector,
            watch=False,
        )
        res = json.loads(api_response.data)
    except ApiException as e:
        _logger.info("Exception when calling CoreV1Api->list_namespaced_job: %s\n" % e)
        raise e

    if "items" not in res:
        return []

    return res["items"]


def list_current_pods(label_selector: str = None):
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    load_kube_config()
    api_instance = CoreV1Api()
    try:
        params: Dict[str, Any] = {}
        params["namespace"] = namespace
        params["_preload_content"] = False
        if label_selector:
            params["label_selector"] = label_selector
        api_response = api_instance.list_namespaced_pod(**params)
        res = json.loads(api_response.data)
    except ApiException as e:
        _logger.info("Exception when calling CoreV1Api->list_namespace_pod: %s\n" % e)
        raise e

    if "items" not in res:
        return []

    return res["items"]


def list_storage_pvc():
    load_kube_config()
    api_instance = CoreV1Api()
    props = get_properties()
    params = dict()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    params["namespace"] = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    params["_preload_content"] = False
    try:
        api_response = api_instance.list_namespaced_persistent_volume_claim(**params)
        res = json.loads(api_response.data)
    except ApiException as e:
        _logger.info("Exception when calling CoreV1Api->list persistent volume claims: %s\n" % e)
        raise e

    if "items" not in res:
        return []

    return res["items"]


def delete_storage_pvc(pvc_name: str):
    load_kube_config()
    api_instance = CoreV1Api()
    props = get_properties()
    params: Dict[str, Any] = {}
    params["name"] = pvc_name
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    params["namespace"] = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    params["_preload_content"] = False
    try:
        api_response = api_instance.delete_namespaced_persistent_volume_claim(**params)
        response = {
            "status": str(api_response.status),
            "reason": api_response.reason,
            "message": f"Successfully deleted persistent volume claim={pvc_name}",
        }
    except ApiException as e:
        _logger.info("Exception when calling CoreV1Api->delete persistent volume claim: %s\n" % e)
        e_body = json.loads(e.body)
        response = {"status": str(e_body["code"]), "reason": e_body["reason"], "message": e_body["message"]}

    return response


def list_storage_pv():
    load_kube_config()
    api_instance = CoreV1Api()
    _logger.debug("Listing cluster persistent volumes")
    params = dict()
    params["_preload_content"] = False
    try:
        api_response = api_instance.list_persistent_volume(**params)
        res = json.loads(api_response.data)
    except ApiException as e:
        _logger.info("Exception when calling CoreV1Api->list persistent volumes : %s\n" % e)
        raise e

    if "items" not in res:
        return []

    return res["items"]


def list_storage_class():
    load_kube_config()
    api_instance = StorageV1Api()
    _logger.debug("Listing cluster storage classes")
    params = dict()
    params["_preload_content"] = False
    try:
        api_response = api_instance.list_storage_class(**params)
        res = json.loads(api_response.data)
    except ApiException as e:
        _logger.info("Exception when calling StorageV1Api->list storage class : %s\n" % e)
        raise e

    if "items" not in res:
        return []

    return res["items"]


def get_nodegroups(cluster_name: str):
    props = get_properties()
    env_name = props["AWS_ORBIT_ENV"]
    nodegroups_with_lt = []
    nodegroups: List[Dict[str, Any]] = []
    _logger.debug(f"Fetching cluster {cluster_name} nodegroups")
    try:
        response: Dict[str, Any] = boto3.client("lambda").invoke(
            FunctionName=f"orbit-{env_name}-eks-service-handler",
            InvocationType="RequestResponse",
            Payload=json.dumps({"cluster_name": cluster_name}).encode("utf-8"),
        )
        if response.get("StatusCode") != 200 or response.get("Payload") is None:
            _logger.error(f"Invalid Lambda response:\n{response}")
            return nodegroups
        nodegroups = json.loads(response["Payload"].read().decode("utf-8"))
    except Exception as ekse:
        _logger.error("Error invoking nodgroup lambda  %s", ekse)
        raise ekse

    # Get launch template details per nodegroup
    ec2_client = boto3.client("ec2")
    for nodegroup in nodegroups:
        try:
            ng = nodegroup
            if "launch_template" in nodegroup:
                ltr_response = ec2_client.describe_launch_template_versions(
                    LaunchTemplateId=nodegroup["launch_template"]["id"],
                    Versions=[nodegroup["launch_template"]["version"]],
                )
                if ltr_response["LaunchTemplateVersions"]:
                    launch_template = ltr_response["LaunchTemplateVersions"][0]
                    ng["launch_template_data"] = launch_template["LaunchTemplateData"]["BlockDeviceMappings"]
                    del ng["launch_template"]

            nodegroups_with_lt.append(ng)
        except Exception as lte:
            _logger.error("Error invoking describe_launch_template_versions  %s", lte)
    return nodegroups_with_lt


def delete_pod(pod_name: str, grace_period_seconds: int = 30):
    props = get_properties()
    global __CURRENT_TEAM_MANIFEST__, __CURRENT_ENV_MANIFEST__
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    load_kube_config()
    api_instance = CoreV1Api()
    try:
        api_instance.delete_namespaced_pod(
            name=pod_name,
            namespace=os.environ.get("AWS_ORBIT_USER_SPACE", team_name),
            _preload_content=False,
            grace_period_seconds=grace_period_seconds,
            orphan_dependents=False,
        )
    except ApiException as e:
        _logger.info("Exception when calling CoreV1Api->delete_namespaced_pod: %s\n" % e)
        raise e


def delete_job(job_name: str, grace_period_seconds: int = 30):
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    api = _dynamic_client().resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    try:
        api.delete(
            name=job_name,
            namespace=os.environ.get("AWS_ORBIT_USER_SPACE", team_name),
            grace_period_seconds=grace_period_seconds,
            orphan_dependents=False,
        )
    except ApiException as e:
        _logger.info("Exception when calling DynamicClient.delete() for OrbitJobs: %s\n" % e)
        raise e


def delete_cronjob(job_name: str, grace_period_seconds: int = 30):
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    api = _dynamic_client().resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    try:
        api.delete(
            name=job_name,
            namespace=os.environ.get("AWS_ORBIT_USER_SPACE", team_name),
            grace_period_seconds=grace_period_seconds,
            orphan_dependents=False,
        )
    except ApiException as e:
        _logger.info("Exception when calling DynamicClient.delete() for OrbitJobs: %s\n" % e)
        raise e


def delete_all_my_pods():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    load_kube_config()
    api_instance = CoreV1Api()
    app_list = ",".join(APP_LABEL_SELECTOR)
    label_selector = f"app in ({app_list})"
    try:
        api_instance.delete_collection_namespaced_pod(
            namespace=namespace, _preload_content=False, orphan_dependents=False, label_selector=label_selector
        )
    except ApiException as e:
        _logger.info("Exception when calling CoreV1Api->delete_collection_namespaced_pod: %s\n" % e)
        raise e


def delete_all_my_jobs():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)

    api = _dynamic_client().resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    label_selector = "k8sJobType=Job"
    try:
        api.delete(namespace=namespace, orphan_dependents=False, label_selector=label_selector)
    except ApiException as e:
        _logger.info("Exception when calling DynamicClient.delete() for OrbitJobs: %s\n" % e)
        raise e


def list_running_cronjobs():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)

    api = _dynamic_client().resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    label_selector = "k8sJobType=CronJob"
    try:
        api_response = api.get(namespace=namespace, label_selector=label_selector)
        res = api_response.to_dict()
    except ApiException as e:
        _logger.info("Exception when calling DynamicClient.get() for OrbitJobs: %s\n" % e)
        raise e

    return [
        oj
        for oj in res.get("items", [])
        if oj.get("status", {}).get("orbitJobOperator", {}).get("jobStatus") == "Active"
    ]


def get_podsetting_spec(podsetting_name, team_name):
    load_kube_config()
    co = CustomObjectsApi()
    return co.get_namespaced_custom_object("orbit.aws", "v1", team_name, "podsettings", podsetting_name)


def get_priority(taskConfiguration: dict):
    if "compute" in taskConfiguration and "priorityClassName" in taskConfiguration["compute"]:
        return taskConfiguration["compute"]["priorityClassName"]


def _create_eks_job_spec(taskConfiguration: dict) -> Dict[str, Any]:
    compute = taskConfiguration.get("compute", {})
    converted_compute = {}
    if "compute_type" in compute:
        converted_compute["computeType"] = compute["compute_type"]
    if "node_type" in compute:
        converted_compute["nodeType"] = compute["node_type"]
    if "env_vars" in compute:
        converted_compute["env"] = compute["env_vars"]
    if "sns.topic.name" in compute:
        converted_compute["snsTopicName"] = compute["sns.topic.name"]
    if "priorityClassName" in compute:
        converted_compute["priorityClassName"] = compute["priorityClassName"]
    if "podsetting" in compute:
        converted_compute["podSetting"] = compute["podsetting"]
    if "labels" in compute:
        converted_compute["labels"] = compute["labels"]
    if "container" in compute:
        if "p_concurrent" in compute["container"]:
            converted_compute["concurrentProcesses"] = compute["container"]["p_concurrent"]

    return {
        "apiVersion": "orbit.aws/v1",
        "kind": "OrbitJob",
        "metadata": {},
        "spec": {
            "taskType": taskConfiguration["task_type"],
            "compute": converted_compute,
            "tasks": taskConfiguration["tasks"],
        },
    }


def resolve_image_from_podsetting(__CURRENT_ENV_MANIFEST__, podsetting_spec):
    if podsetting_spec and "spec" in podsetting_spec and "image" in podsetting_spec["spec"]:
        image = podsetting_spec["spec"]["image"]
    else:
        repository = (
            f'{__CURRENT_ENV_MANIFEST__["Images"]["JupyterUser"]["Repository"]}:'
            f'{__CURRENT_ENV_MANIFEST__["Images"]["JupyterUser"]["Version"]}'
        )
        image = f"{repository}"
    return image


def resolve_image(__CURRENT_ENV_MANIFEST__, profile):

    if not profile or "kubespawner_override" not in profile or "image" not in profile["kubespawner_override"]:
        repository = (
            f'{__CURRENT_ENV_MANIFEST__["Images"]["JupyterUser"]["Repository"]}:'
            f'{__CURRENT_ENV_MANIFEST__["Images"]["JupyterUser"]["Version"]}'
        )
        image = f"{repository}"
    else:
        image = profile["kubespawner_override"]["image"]
    return image


def build_env(__CURRENT_ENV_MANIFEST__, env_name, taskConfiguration, team_name):
    env = dict()
    env["task_type"] = taskConfiguration["task_type"]
    env["tasks"] = json.dumps({"tasks": taskConfiguration["tasks"]})
    if "compute" in taskConfiguration:
        env["compute"] = json.dumps({"compute": taskConfiguration["compute"]})
    else:
        env["compute"] = json.dumps({"compute": {"compute_type": "eks", "node_type": "fargate"}})
    return env


def resolve_podsetting_name(taskConfiguration):
    if "compute" in taskConfiguration and "podsetting" in taskConfiguration["compute"]:
        return taskConfiguration["compute"]["podsetting"]


def _run_task_eks(taskConfiguration: dict) -> Any:
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
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    node_type = get_node_type(taskConfiguration)
    job_spec = _create_eks_job_spec(taskConfiguration)
    job_spec["spec"]["notebookName"] = os.environ.get("HOSTNAME", "")
    job_spec["metadata"]["generateName"] = f"orbit-{team_name}-{node_type}-runner-"

    dynamic_client = _dynamic_client()
    api = dynamic_client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    job_instance = api.create(namespace=namespace, body=job_spec).to_dict()

    metadata = job_instance["metadata"]
    _logger.debug(f"started job {metadata['name']}")
    return {
        "ExecutionType": "eks",
        "Identifier": metadata["name"],
        "NodeType": node_type,
        "tasks": taskConfiguration["tasks"],
    }


def schedule_python(triggerName: str, frequency: str, taskConfiguration: Dict[str, Any]) -> str:
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
    if "compute_type" not in taskConfiguration or taskConfiguration["compute_type"] == "eks":
        return schedule_task_eks(triggerName, frequency, taskConfiguration)
    else:
        raise RuntimeError("Unsupported compute_type '%s'", taskConfiguration["compute_type"])


def schedule_notebooks(triggerName: str, frequency: str, taskConfiguration: dict) -> str:
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
    if "compute_type" not in taskConfiguration or taskConfiguration["compute_type"] == "eks":
        return schedule_task_eks(triggerName, frequency, taskConfiguration)
    else:
        raise RuntimeError("Unsupported compute_type '%s'", taskConfiguration["compute_type"])


def get_node_type(taskConfiguration) -> str:
    if "compute" not in taskConfiguration or "node_type" not in taskConfiguration["compute"]:
        node_type = "fargate"
    else:
        node_type = taskConfiguration["compute"]["node_type"]

    return node_type


def schedule_task_eks(triggerName: str, frequency: str, taskConfiguration: dict) -> Any:
    """
    Parameters
    ----------
    triggerName: str
        A unique name of the time trigger that will start this exec
    frequency: str
        A cron string e.g., cron(0/15 * 1/1 * ? *) to define the starting times of the execution
    taskConfiguration: Any
    Return
    ------
    Example
    -------
    Example for schedule_task similar to run_python and run_notebook tasks (refer to 'run_python').
    """
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    job_spec = _create_eks_job_spec(taskConfiguration)
    job_spec["spec"]["schedule"] = frequency
    job_spec["spec"]["triggerName"] = triggerName
    job_spec["spec"]["notebookName"] = "schduled"
    job_spec["metadata"]["name"] = f"orbit-{namespace}-{triggerName}"

    dynamic_client = _dynamic_client()
    api = dynamic_client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    job_instance = api.create(namespace=namespace, body=job_spec).to_dict()

    metadata = job_instance["metadata"]
    _logger.debug(f"started job {metadata['name']}")
    return {
        "ExecutionType": "eks",
        "Identifier": metadata["name"],
    }


def load_kube_config():
    if "AWS_WEB_IDENTITY_TOKEN_FILE" in os.environ and "eks.amazonaws.com" in os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"]:
        k8_config.load_incluster_config()
    else:
        k8_config.load_kube_config()


def delete_task_schedule(triggerName: str, compute_type: str = "eks") -> None:
    if compute_type == "eks":
        return delete_task_schedule_eks(triggerName)
    else:
        raise RuntimeError("Unsupported compute_type '%s'", compute_type)


def delete_task_schedule_eks(triggerName: str) -> None:
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)

    dynamic_client = _dynamic_client()
    api = dynamic_client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    api.delete(name=f"orbit-{team_name}-{triggerName}", namespace=namespace)


# def order_def(task_definition: Any) -> datetime:
#     """
#     Order task definitions by their timestamps of when they start at.

#     Parameters
#     -----------
#     task_definition: Any

#     Returns
#     --------
#     date : datetime
#         Timestamp for a specific task definition, or the current timestamp if one does not already exist.
#     """

#     if "epoch" in task_definition:
#         return task_definition["epoch"]
#     return datetime.now().timestamp()


def wait_for_tasks_to_complete(
    tasks: List[Any],
    delay: int = 10,
    maxAttempts: int = 10,
    tail_log: bool = False,
) -> bool:
    """
    Parameters
    ----------
    tasks: lst
       A list of structures with container type, execution arn, and job arn.
    delay: int
       Number of seconds to wait until checking containers state again (default = 60).
    maxAttempts: int
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
    controller.wait_for_tasks_to_complete(containers, 60,40)
    """

    completed_tasks = []
    errored_tasks = []
    attempts = 0
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]

    incomplete_tasks = []
    _logger.info("Waiting for %s tasks %s", len(tasks), tasks)
    namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
    api = _dynamic_client().resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="OrbitJob")
    time.sleep(delay)
    while True:
        for task in tasks:
            _logger.debug("Checking execution state of: %s", task)
            try:
                current_jobs = api.get(namespace=namespace)
            except exceptions.ApiException as e:
                _logger.error("Error during list jobs for %s: %s", team_name, e)
                # try again after 5 seconds.
                time.sleep(5)
                current_jobs = api.get(namespace=namespace)
            task_name = task["Identifier"]
            for job in current_jobs["items"]:
                _logger.debug(f"orbit_job={job}")
                job_metadata = job["metadata"]
                job_status = job["status"].get("orbitJobOperator", {})
                if job_metadata["name"] != task["Identifier"]:
                    continue
                _logger.debug(f"job-status={job_status}")
                if job_status.get("jobStatus") == "Active":
                    incomplete_tasks.append(task)
                    _logger.info("Task %s is running with status %s", task, job_status)
                elif job_status.get("jobStatus") == "Failed":
                    _logger.debug(f"Execution error: {task_name}")
                    errored_tasks.append(task)
                elif job_status.get("jobStatus") == "Complete":
                    completed_tasks.append(task)
                else:
                    incomplete_tasks.append(task)

            if tail_log:
                tail_logs(team_name, tasks)

        tasks = incomplete_tasks
        incomplete_tasks = []
        _logger.info(f"Running: {len(tasks)} Completed: {len(completed_tasks)} Errored: {len(errored_tasks)}")

        attempts += 1
        if len(tasks) == 0:
            _logger.info("All tasks stopped")
            return len(errored_tasks) == 0
        elif attempts >= maxAttempts:
            _logger.info("Stopped waiting as maxAttempts reached")
            return len(errored_tasks) > 0
        else:
            _logger.info("waiting for %s", tasks)
            time.sleep(delay)
            load_kube_config()


def tail_logs(team_name, tasks) -> None:
    for task in tasks:
        task_id = task["Identifier"]
        _logger.info("Watching task: '%s'", task_id)
        namespace = os.environ.get("AWS_ORBIT_USER_SPACE", team_name)
        current_pods: V1PodList = CoreV1Api().list_namespaced_pod(
            namespace=namespace, label_selector=f"job-name={task_id}"
        )
        for pod in current_pods.items:
            pod_instance: V1Pod = cast(V1Pod, pod)
            _logger.debug("pod: %s", pod_instance.metadata.name)
            pod_status: V1PodStatus = cast(V1PodStatus, pod_instance.status)
            _logger.debug("pod s: %s", pod_status)
            if pod_status.conditions:
                for c in pod_status.conditions:
                    condition: V1PodCondition = cast(V1PodCondition, c)
                    if condition.type == "Failed" or condition.reason == "Unschedulable":
                        _logger.info("pod has error status %s , %s", condition.reason, condition.message)
                        return
            if pod_status.container_statuses:
                for s in pod_status.container_statuses:
                    container_status: V1ContainerStatus = cast(V1ContainerStatus, s)
                    container_state: V1ContainerState = container_status.state
                    _logger.debug("task status: %s ", container_status)
                    if container_status.started or container_state.running or container_state.terminated:
                        _logger.info("task %s status: %s", pod_instance.metadata.name, container_state)
                        w = k8_watch.Watch()
                        for line in w.stream(
                            CoreV1Api().read_namespaced_pod_log, name=pod_instance.metadata.name, namespace=namespace
                        ):
                            _logger.info(line)
                    else:
                        _logger.info("task not started yet for %s", task_id)


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
    logging.basicConfig(format="%(message)s", level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")

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
                t = datetime.fromtimestamp(e["timestamp"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                m = e["message"]
                _logger.info(t, m)
                lastTime = e["timestamp"]

            if "nextToken" in page.keys():
                marker = page["nextToken"]
            else:
                marker = None

        if marker is None:
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


def build_podsetting(env_name: str, team_name: str, podsetting: str, debug: bool) -> None:
    ps = json.loads(podsetting)
    if not ps["description"] or not ps["name"]:
        raise Exception("Podsetting name and description not present")
    podsetting_name = ps["name"]
    spec_template = _generate_podsetting_spec_base(
        podsetting_name=podsetting_name, description=ps["description"], env_name=env_name, team_name=team_name
    )
    spec = yaml.load(spec_template, Loader=yaml.SafeLoader)
    env_params = ps.get("env", None)
    if env_params:
        spec["spec"]["env"] = env_params

    image = ps.get("image", None)
    if image:
        spec["spec"]["image"] = image

    resources = ps.get("resources", None)
    if resources is not None:
        spec["spec"]["resources"] = resources

    nodegroup = ps.get("node-group", None)
    instancetype = ps.get("instance-type", None)
    if nodegroup or instancetype:
        spec["spec"]["nodeSelector"] = {}
        if nodegroup:
            spec["spec"]["nodeSelector"]["orbit/node-group"] = nodegroup
        if instancetype:
            spec["spec"]["nodeSelector"]["node.kubernetes.io/instance-type"] = instancetype

    _logger.debug(yaml.dump(spec))

    dynamic_client = _dynamic_client()
    # This is a hack....we cannot update/patch so delete and create (for now)
    try:
        _destroy_podsetting(namespace=team_name, podsetting_name=podsetting_name, client=dynamic_client)
        time.sleep(3)
    except ApiException:
        _logger.info(f"Tried to delete {podsetting_name} but that podsetting was not found...moving on")

    _deploy_podsetting(namespace=team_name, name=podsetting_name, client=dynamic_client, podsetting_spec=spec)
    _logger.info(f"PodSetting {podsetting_name} deployed to {team_name}")


def delete_podsetting(namespace: str, podsetting_name: str) -> None:
    try:
        _destroy_podsetting(namespace, podsetting_name, client=_dynamic_client())
    except ApiException as e:
        _logger.info(f"PodSetting {podsetting_name} failed to delete - : {e}")


def _deploy_podsetting(
    namespace: str, name: str, client: dynamic.DynamicClient, podsetting_spec: Dict[str, Any]
) -> None:
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="PodSetting")
    api.create(namespace=namespace, body=podsetting_spec)


def _destroy_podsetting(namespace: str, podsetting_name: str, client: dynamic.DynamicClient) -> None:
    api = client.resources.get(api_version=ORBIT_API_VERSION, group=ORBIT_API_GROUP, kind="PodSetting")
    api.delete(namespace=namespace, name=podsetting_name, body={})


def _dynamic_client() -> dynamic.DynamicClient:
    load_kube_config()
    return dynamic.DynamicClient(client=api_client.ApiClient())


def _generate_podsetting_spec_base(podsetting_name, description, env_name, team_name):
    spec_template = """
        kind: PodSetting
        apiVersion: orbit.aws/v1
        metadata:
            labels:
                orbit/env: {env_name}
                orbit/space: team
                orbit/team: {team_name}
            name: {podsetting_name}
            namespace: {team_name}
        spec:
            containerSelector:
                jsonpath: metadata.labels.app
            desc: {description}
            podSelector:
                matchExpressions:
                - key: orbit/{podsetting_name}
                  operator: Exists
            securityContext:
                runAsUser: 1000
    """.format(
        team_name=team_name, description=description, env_name=env_name, podsetting_name=podsetting_name
    )
    return spec_template
