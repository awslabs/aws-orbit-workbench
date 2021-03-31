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
import sys
import time
import urllib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import boto3
import botocore
import pandas as pd
from kubernetes import config as k8_config
from kubernetes import watch as k8_watch
from kubernetes.client import *
from kubespawner.objects import make_pod, make_pvc
from slugify import slugify

from aws_orbit_sdk.common import get_properties, get_stepfunctions_waiter_config
from aws_orbit_sdk.common_pod_specification import TeamConstants

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
_logger = logging.getLogger()

MANIFEST_PLUGIN_TYPE = Dict[str, Union[str, Dict[str, Any]]]
MANIFEST_PROPERTY_MAP_TYPE = Dict[str, Union[str, Dict[str, Any]]]
MANIFEST_FILE_TEAM_TYPE = Dict[str, Union[str, int, None, List[MANIFEST_PROPERTY_MAP_TYPE], List[str]]]
MANIFEST_TEAM_TYPE = Dict[str, Union[str, int, None, List[MANIFEST_PLUGIN_TYPE]]]
MANIFEST_PROPERTY_MAP_TYPE = Dict[str, Union[str, Dict[str, Any]]]

__CURRENT_TEAM_MANIFEST__: MANIFEST_TEAM_TYPE = None
__CURRENT_ENV_MANIFEST__: MANIFEST_TEAM_TYPE = None


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
    except botocore.errorfactory.ParameterNotFound as e:
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


def _get_execution_history_from_s3(notebookBaseDir: str, srcNotebook: str, props: str) -> pd.DataFrame:
    """
    Get Notebook Execution History from s3
    """
    s3 = boto3.client("s3")

    notebookDir = os.path.join(notebookBaseDir, srcNotebook.split(".")[0])

    path = "{}/output/notebooks/{}/".format(props["AWS_ORBIT_TEAM_SPACE"], notebookDir)
    executions = []
    objects = s3.list_objects_v2(Bucket=props["AWS_ORBIT_S3_BUCKET"], Prefix=path)
    if "Contents" in objects.keys():
        for key in s3.list_objects_v2(Bucket=props["AWS_ORBIT_S3_BUCKET"], Prefix=path)["Contents"]:
            if key["Key"][-1] == "/":
                continue
            notebookName = os.path.basename(key["Key"])
            path = key["Key"]
            arg = urllib.parse.quote(path)
            s3path = "s3://{}/{}".format(props["AWS_ORBIT_S3_BUCKET"], path)
            #     link = '<a href="{}" target="_blank">{}</a>'.format(site + arg,"open")
            timestamp = key["LastModified"]
            executions.append((notebookName, timestamp, s3path))
    else:
        _logger.info("No output notebooks founds at: s3://{}/{}".format(props["AWS_ORBIT_S3_BUCKET"], path))

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
    functionName = f"orbit-{props['AWS_ORBIT_ENV']}-{props['AWS_ORBIT_TEAM_SPACE']}-container-runner"
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
    if "compute_type" not in taskConfiguration or taskConfiguration["compute_type"] == "eks":
        return _run_task_eks(taskConfiguration)
    else:
        raise RuntimeError("Unsupported compute_type '%s'", taskConfiguration["compute_type"])


def list_team_running_jobs():
    return list_running_jobs(True)


def list_my_running_jobs():
    return list_running_jobs(False)


def list_running_jobs(team_only: bool = False):
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    load_kube_config()
    username = os.environ.get("JUPYTERHUB_USER", os.environ.get("USERNAME"))
    api_instance = BatchV1Api()
    # field_selector = "status.successful!=1"
    if team_only:
        operand = "!="
    else:
        operand = "="

    label_selector = f"app=orbit-runner,username{operand}{username}"
    _logger.info("using job selector %s", label_selector)
    try:
        api_response = api_instance.list_namespaced_job(
            namespace=team_name,
            _preload_content=False,
            label_selector=label_selector,
            # field_selector=field_selector,
            watch=False,
        )
        res = json.loads(api_response.data)
    except ApiException as e:
        _logger.info("Exception when calling BatchV1Api->list_namespaced_job: %s\n" % e)
        raise e

    if "items" not in res:
        return []

    return res["items"]


def list_current_pods(label_selector: str = None):
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    load_kube_config()
    api_instance = CoreV1Api()
    try:
        params = dict()
        params["namespace"] = team_name
        params["_preload_content"] = False
        if label_selector:
            params["label_selector"] = label_selector
        api_response = api_instance.list_namespaced_pod(**params)
        res = json.loads(api_response.data)
    except ApiException as e:
        _logger.info("Exception when calling BatchV1Api->list_namespaced_job: %s\n" % e)
        raise e

    if "items" not in res:
        return []

    return res["items"]


def list_storage_pvc():
    load_kube_config()
    api_instance = CoreV1Api()
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    _logger.debug(f"Listing {team_name} namespace persistent volume claims")
    params = dict()
    params["namespace"] = team_name
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
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    _logger.debug(f"Deleting {team_name} namespace persistent volume claim {pvc_name}")
    params = dict()
    params["name"] = pvc_name
    params["namespace"] = team_name
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


def delete_job(job_name: str, grace_period_seconds: int = 30):
    props = get_properties()
    global __CURRENT_TEAM_MANIFEST__, __CURRENT_ENV_MANIFEST__
    env_name = props["AWS_ORBIT_ENV"]
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    load_kube_config()
    api_instance = BatchV1Api()
    try:
        api_instance.delete_namespaced_job(
            name=job_name,
            namespace=team_name,
            _preload_content=False,
            grace_period_seconds=grace_period_seconds,
            orphan_dependents=False,
        )
    except ApiException as e:
        _logger.info("Exception when calling BatchV1Api->list_namespaced_job: %s\n" % e)
        raise e


def delete_cronjob(job_name: str, grace_period_seconds: int = 30):
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    load_kube_config()
    api_instance = BatchV1beta1Api()
    try:
        api_instance.delete_namespaced_cron_job(
            name=job_name,
            namespace=team_name,
            _preload_content=False,
            grace_period_seconds=grace_period_seconds,
            orphan_dependents=False,
        )
    except ApiException as e:
        _logger.info("Exception when calling BatchV1Api->delete_namespaced_cron_job: %s\n" % e)
        raise e


def delete_all_my_jobs():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    username = os.environ.get("JUPYTERHUB_USER", os.environ.get("USERNAME"))
    load_kube_config()
    api_instance = BatchV1Api()
    label_selector = f"app=orbit-runner,username={username}"
    try:
        api_instance.delete_collection_namespaced_job(
            namespace=team_name, _preload_content=False, orphan_dependents=False, label_selector=label_selector
        )
    except ApiException as e:
        _logger.info("Exception when calling BatchV1Api->delete_collection_namespaced_job: %s\n" % e)
        raise e


def list_running_cronjobs():
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    load_kube_config()
    api_instance = BatchV1beta1Api()
    try:
        api_response = api_instance.list_namespaced_cron_job(namespace=team_name, _preload_content=False)
        res = json.loads(api_response.data)
    except ApiException as e:
        _logger.info("Exception when calling BatchV1beta1Api->list_namespaced_cron_job: %s\n" % e)
        raise e

    if "items" not in res:
        return []

    return res["items"]


def _create_eks_job_spec(taskConfiguration: dict, labels: Dict[str, str], team_constants: TeamConstants) -> V1JobSpec:
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
    global __CURRENT_TEAM_MANIFEST__, __CURRENT_ENV_MANIFEST__
    env_name = props["AWS_ORBIT_ENV"]
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    if __CURRENT_TEAM_MANIFEST__ == None or __CURRENT_TEAM_MANIFEST__["Name"] != team_name:
        __CURRENT_TEAM_MANIFEST__ = load_team_context_from_ssm(env_name, team_name)
    if __CURRENT_ENV_MANIFEST__ == None:
        __CURRENT_ENV_MANIFEST__ = load_env_context_from_ssm(env_name)

    env = build_env(__CURRENT_ENV_MANIFEST__, env_name, taskConfiguration, team_constants, team_name)
    profile = resolve_profile(taskConfiguration, team_constants)
    image = resolve_image(__CURRENT_TEAM_MANIFEST__, profile)
    node_type = get_node_type(taskConfiguration)

    job_name: str = f'run-{taskConfiguration["task_type"]}'
    volumes = team_constants.volumes()
    volume_mounts = team_constants.volume_mounts()
    grant_sudo = False
    if "kubespawner_override" in profile:
        if "volumes" in profile["kubespawner_override"]:
            volumes.extend(profile["kubespawner_override"]["volumes"])
            _logger.info("profile override is attaching volumes: %s", volumes)
        if "volume_mounts" in profile["kubespawner_override"]:
            volume_mounts.extend(profile["kubespawner_override"]["volume_mounts"])
            _logger.info("profile override is mounting volumes: %s", volume_mounts)
    if "compute" in taskConfiguration:
        if "grant_sudo" in taskConfiguration["compute"]:
            if taskConfiguration["compute"]["grant_sudo"] or taskConfiguration["compute"]["grant_sudo"] == "True":
                grant_sudo = True
        if "volumes" in taskConfiguration["compute"]:
            volumes.extend(taskConfiguration["compute"]["volumes"])
            _logger.info("task override is attaching volumes: %s", volumes)
        if "volume_mounts" in taskConfiguration["compute"]:
            volume_mounts.extend(taskConfiguration["compute"]["volume_mounts"])
            _logger.info("task override is mounting volumes: %s", volume_mounts)
        if "labels" in taskConfiguration["compute"]:
            labels = {**labels, **taskConfiguration["compute"]["labels"]}
    node_selector = team_constants.node_selector(node_type)
    _logger.info("volumes:%s", json.dumps(volumes))
    _logger.info("volume_mounts:%s", json.dumps(volume_mounts))
    pod_properties: Dict[str, str] = dict(
        name=job_name,
        image=image,
        cmd=["bash", "-c", "/home/jovyan/.orbit/bootstrap.sh && python /opt/python-utils/notebook_cli.py"],
        port=22,
        image_pull_policy=team_constants.image_pull_policy(),
        image_pull_secrets=None,
        node_selector=node_selector,
        run_as_uid=team_constants.uid(grant_sudo),
        run_as_gid=team_constants.gid(),
        fs_gid=team_constants.gid(),
        run_privileged=False,
        allow_privilege_escalation=True,
        env=env,
        volumes=volumes,
        volume_mounts=volume_mounts,
        labels=labels,
        annotations=team_constants.annotations(),
        lifecycle_hooks=team_constants.life_cycle_hooks(),
        service_account=team_name,
        logger=_logger,
    )
    if grant_sudo:
        pod_properties["uid"] = 0

    if "kubespawner_override" in profile:
        for k, v in profile["kubespawner_override"].items():
            if k in ["image"]:
                # special handling is already done for image
                continue
            if k in pod_properties:
                raise RuntimeError("Override '%s' in profile is not allowed", k)
            _logger.debug("profile overriding pod value %s=%s", k, v)
            pod_properties[k] = v

    pod: V1Pod = make_pod(**pod_properties)
    pod.spec.restart_policy = "Never"
    job_spec = V1JobSpec(
        backoff_limit=0,
        template=pod,
        ttl_seconds_after_finished=120,
    )

    return job_spec


def resolve_image(__CURRENT_TEAM_MANIFEST__, profile):
    if not profile or "kubespawner_override" not in profile or "image" not in profile["kubespawner_override"]:
        repository = __CURRENT_TEAM_MANIFEST__["FinalImageAddress"]
        image = f"{repository}"
    else:
        image = profile["kubespawner_override"]["image"]
    return image


def build_env(__CURRENT_ENV_MANIFEST__, env_name, taskConfiguration, team_constants, team_name):
    env = team_constants.env()
    env["AWS_ORBIT_ENV"] = env_name
    env["AWS_ORBIT_TEAM_SPACE"] = team_name
    env["JUPYTERHUB_USER"] = team_constants.username
    env["USERNAME"] = team_constants.username
    env["AWS_ORBIT_S3_BUCKET"] = __CURRENT_ENV_MANIFEST__["Toolkit"]["S3Bucket"]
    env["task_type"] = taskConfiguration["task_type"]
    env["tasks"] = json.dumps({"tasks": taskConfiguration["tasks"]})
    if "compute" in taskConfiguration:
        env["compute"] = json.dumps({"compute": taskConfiguration["compute"]})
    else:
        env["compute"] = json.dumps({"compute": {"compute_type": "eks", "node_type": "fargate"}})
    return env


def resolve_profile(taskConfiguration, team_constants):
    if "compute" in taskConfiguration and "profile" in taskConfiguration["compute"]:
        profile_name = taskConfiguration["compute"]["profile"]
        profile_name = slugify(profile_name)
        _logger.info(f"using profile %s", profile_name)
        profile = team_constants.profile(profile_name)
        if not profile:
            raise Exception("Profile '%s' not found", profile)
    else:
        profile = team_constants.default_profile()
        _logger.info(f"using default profile %s", profile)
    return profile


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
    username = os.environ.get("JUPYTERHUB_USER", os.environ.get("USERNAME"))
    node_type = get_node_type(taskConfiguration)
    labels = {"app": f"orbit-runner", "orbit/node-type": node_type, "username": username}
    if node_type == "ec2":
        labels["orbit/attach-security-group"] = "yes"
    team_constants: TeamConstants = TeamConstants()
    job_spec = _create_eks_job_spec(taskConfiguration, labels=labels, team_constants=team_constants)
    load_kube_config()
    if "compute" in taskConfiguration:
        if "labels" in taskConfiguration["compute"]:
            labels = {**labels, **taskConfiguration["compute"]["labels"]}
    job = V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=V1ObjectMeta(
            generate_name=f"orbit-{team_name}-{node_type}-runner-", labels=labels, namespace=team_name
        ),
        spec=job_spec,
    )
    job_instance: V1Job = BatchV1Api().create_namespaced_job(
        namespace=team_name,
        body=job,
    )
    metadata: V1ObjectMeta = job_instance.metadata

    _logger.debug(f"started job {metadata.name}")
    return {
        "ExecutionType": "eks",
        "Identifier": metadata.name,
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
    node_type = get_node_type(taskConfiguration)
    username = os.environ.get("JUPYTERHUB_USER", os.environ.get("USERNAME"))
    cronjob_id = f"orbit-{team_name}-{triggerName}"
    labels = {"app": f"orbit-runner", "orbit/node-type": node_type, "username": username, "cronjob_id": cronjob_id}
    team_constants: TeamConstants = TeamConstants(username)
    job_spec = _create_eks_job_spec(taskConfiguration, labels=labels, team_constants=team_constants)
    cron_job_template: V1beta1JobTemplateSpec = V1beta1JobTemplateSpec(spec=job_spec)
    cron_job_spec: V1beta1CronJobSpec = V1beta1CronJobSpec(job_template=cron_job_template, schedule=frequency)
    job = V1beta1CronJob(
        api_version="batch/v1beta1",
        kind="CronJob",
        metadata=V1ObjectMeta(name=cronjob_id, labels=labels, namespace=team_name),
        status=V1beta1CronJobStatus(),
        spec=cron_job_spec,
    )
    load_kube_config()

    job_instance: V1beta1CronJob = BatchV1beta1Api().create_namespaced_cron_job(namespace=team_name, body=job)
    metadata: V1ObjectMeta = job_instance.metadata
    return {
        "ExecutionType": "eks",
        "Identifier": metadata.name,
    }
    metadata: V1ObjectMeta = job_instance.metadata
    _logger.debug(f"started job {metadata.name}")


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
    load_kube_config()

    BatchV1beta1Api().delete_namespaced_cron_job(name=f"orbit-{team_name}-{triggerName}", namespace=team_name)


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
    delay: Optional[int] = 10,
    maxAttempts: Optional[int] = 10,
    tail_log: Optional[bool] = False,
) -> bool:
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
    controller.wait_for_tasks_to_complete(containers, 60,40)
    """

    completed_tasks = []
    errored_tasks = []
    attempts = 0
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]

    incomplete_tasks = []
    _logger.info("Waiting2 for %s tasks %s", len(tasks), tasks)
    load_kube_config()
    while True:
        for task in tasks:
            _logger.debug("Checking execution state of: %s", task)
            try:
                current_jobs: V1JobList = BatchV1Api().list_namespaced_job(
                    namespace=team_name, label_selector=f"app=orbit-runner"
                )
            except exceptions.ApiException as e:
                _logger.error("Error during list jobs for %s: %s", team_name, e)
                # try again after 5 seconds.
                time.sleep(5)
                current_jobs: V1JobList = BatchV1Api().list_namespaced_job(
                    namespace=team_name, label_selector=f"app=orbit-runner"
                )
            task_name = task["Identifier"]
            for job in current_jobs.items:
                job_instance: V1Job = cast(V1Job, job)
                job_metadata: V1ObjectMeta = cast(V1ObjectMeta, job_instance.metadata)
                if job_metadata.name != task["Identifier"]:
                    continue
                job_status: V1JobStatus = cast(V1JobStatus, job_instance.status)
                _logger.debug(f"job-status={job_status}")
                if job_status.active == 1:
                    incomplete_tasks.append(task)
                    _logger.info("Task %s is running with status %s", task, job_status)
                elif job_status.failed == 1:
                    _logger.debug(f"Execution error: {task_name}")
                    errored_tasks.append(task)
                elif job_status.succeeded:
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

        current_pods: V1PodList = CoreV1Api().list_namespaced_pod(
            namespace=team_name, label_selector=f"job-name={task_id}"
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
                            CoreV1Api().read_namespaced_pod_log, name=pod_instance.metadata.name, namespace=team_name
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
                t = datetime.fromtimestamp(e["timestamp"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
                m = e["message"]
                _logger.info(t, m)
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
