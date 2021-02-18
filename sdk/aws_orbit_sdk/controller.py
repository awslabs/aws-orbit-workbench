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
import pandas as pd
from botocore.waiter import WaiterModel, create_waiter_with_client
from kubernetes import client as k8_client
from kubernetes import config as k8_config
from kubernetes import watch as k8_watch
from kubernetes.client import *

from aws_orbit_sdk.common import get_properties, get_stepfunctions_waiter_config
from aws_orbit_sdk.CommonPodSpecification import TeamConstants

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


def read_raw_manifest_ssm(env_name: str, team_name: str) -> Optional[MANIFEST_TEAM_TYPE]:
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
        print(f"No output notebooks founds at: {notebook_dir}")

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
        print("No output notebooks founds at: s3://{}/{}".format(props["AWS_ORBIT_S3_BUCKET"], path))

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
    elif taskConfiguration["compute_type"] == "ecs":
        return _run_task_ecs(taskConfiguration)
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
    elif taskConfiguration["compute_type"] == "ecs":
        return _run_task_ecs(taskConfiguration)
    else:
        raise RuntimeError("Unsupported compute_type '%s'", taskConfiguration["compute_type"])


def make_pvc(
    pvc_name,
    team_name,
    storage_class,
    access_modes,
    selector,
    storage,
    labels=None,
) -> V1PersistentVolumeClaim:
    """
    Make a k8s pvc specification for running a user notebook.

    Parameters
    ----------
    name:
        Name of persistent volume claim. Must be unique within the namespace the object is
        going to be created in. Must be a valid DNS label.
    storage_class:
        String of the name of the k8s Storage Class to use.
    access_modes:
        A list of specifying what access mode the pod should have towards the pvc
    selector:
        Dictionary Selector to match pvc to pv.
    storage:
        The ammount of storage needed for the pvc

    """
    pvc = V1PersistentVolumeClaim()
    pvc.kind = "PersistentVolumeClaim"
    pvc.api_version = "v1"
    user_name = os.environ["USERNAME"]
    pvc.metadata = V1ObjectMeta(
        name=pvc_name,
        labels=labels,
        namespace=team_name,
        annotations={
            "AWS_ORBIT_TEAM_SPACE": team_name,
            "USERNAME": user_name,
            "volume.beta.kubernetes.io/storage-class": storage_class,
        },
    )
    pvc.spec = V1PersistentVolumeClaimSpec()
    pvc.spec.access_modes = access_modes
    pvc.spec.resources = V1ResourceRequirements()
    pvc.spec.resources.requests = {"storage": storage}
    pvc.spec.storage_class_name = storage_class

    if selector:
        pvc.spec.selector = selector

    return pvc


def _make_create_pvc_request(team_name, labels):
    user_name = os.environ["USERNAME"]
    pvc_name = f"orbit-{user_name}"
    pvc = make_pvc(
        pvc_name=pvc_name,
        team_name=team_name,
        labels=labels,
        storage_class=f"ebs-{team_name}-gp2",
        access_modes=["ReadWriteOnce"],
        storage="5Gi",
        selector={},
    )
    # Try and create the pvc. If it succeeds we are good. If
    # returns a 409 indicating it already exists we are good. If
    # it returns a 403, indicating potential quota issue we need
    # to see if pvc already exists before we decide to raise the
    # error for quota being exceeded. This is because quota is
    # checked before determining if the PVC needed to be
    # created.
    try:
        pvc_instance = CoreV1Api().create_namespaced_persistent_volume_claim(namespace=team_name, body=pvc)
        metadata: V1ObjectMeta = pvc_instance.metadata
        return True
    except ApiException as e:
        if e.status == 409:
            _logger.info("PVC " + pvc_name + " already exists, so did not create new pvc.")
            return True
        elif e.status == 403:
            t, v, tb = sys.exc_info()
            try:
                CoreV1Api().read_namespaced_persistent_volume_claim_status(namespace=team_name, name=metadata.name)
            except ApiException as e:
                raise v.with_traceback(tb)
            _logger.info("PVC " + pvc_name + " already exists, possibly have reached quota though.")
            return True
        else:
            raise


def _get_job_spec(
    job_name: str,
    team_name: str,
    cmds: List[str],
    env_vars: Dict[str, Any],
    image: str,
    node_type: str,
    labels: Dict[str, str],
    team_constants: TeamConstants = TeamConstants(),
) -> V1JobSpec:
    container = V1Container(
        name=job_name,
        image=image,
        command=cmds,
        env=[V1EnvVar(name=k, value=v) for k, v in env_vars.items()],
        volume_mounts=[
            V1VolumeMount(name="efs-volume", mount_path="/efs"),
            V1VolumeMount(name="ebs-volume", mount_path="/ebs"),
        ],
        resources=V1ResourceRequirements(limits={"cpu": 1, "memory": "2G"}, requests={"cpu": 1, "memory": "2G"}),
        security_context=V1SecurityContext(run_as_user=1000),
        lifecycle=team_constants.life_cycle_hooks(),
    )
    user_name = os.environ["USERNAME"]
    volumes = [
        V1Volume(
            name="efs-volume",
            persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(claim_name="jupyterhub"),
        ),
        V1Volume(
            name="ebs-volume",
            persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(claim_name=f"orbit-{user_name}"),
        ),
    ]
    init_containers = team_constants.init_containers(image)
    pod_spec = V1PodSpec(
        restart_policy="Never",
        containers=[container],
        volumes=volumes,
        node_selector={"orbit/usage": "teams"},
        service_account=team_name,
        security_context=V1PodSecurityContext(fs_group=1000),
        init_containers=init_containers,
    )
    if node_type == "ec2":
        pod_spec.node_selector = {
            "orbit/usage": "teams",
            "orbit/node-type": "ec2",
        }
        labels["orbit/attach-security-group"] = "yes"

    pod = V1PodTemplateSpec(metadata=V1ObjectMeta(labels=labels, namespace=team_name), spec=pod_spec)

    job_spec = V1JobSpec(
        backoff_limit=0,
        template=pod,
        ttl_seconds_after_finished=120,
    )

    return job_spec


def _create_eks_job_spec(taskConfiguration: dict, labels: Dict[str, str]) -> V1JobSpec:
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
    team_constants: TeamConstants = TeamConstants()

    env = dict()

    env_name = env["AWS_ORBIT_ENV"] = props["AWS_ORBIT_ENV"]
    team_name = env["AWS_ORBIT_TEAM_SPACE"] = props["AWS_ORBIT_TEAM_SPACE"]
    env["JUPYTERHUB_USER"] = os.environ["JUPYTERHUB_USER"] if os.environ["JUPYTERHUB_USER"] else os.environ["USERNAME"]
    env["USERNAME"] = env["JUPYTERHUB_USER"]
    env["AWS_STS_REGIONAL_ENDPOINTS"] = "regional"
    env["task_type"] = taskConfiguration["task_type"]
    env["tasks"] = json.dumps({"tasks": taskConfiguration["tasks"]})
    if "compute" in taskConfiguration:
        env["compute"] = json.dumps({"compute": taskConfiguration["compute"]})
    else:
        env["compute"] = json.dumps({"compute": {"compute_type": "eks", "node_type": "fargate"}})

    global __CURRENT_TEAM_MANIFEST__

    if __CURRENT_TEAM_MANIFEST__ == None or __CURRENT_TEAM_MANIFEST__["name"] != team_name:
        __CURRENT_TEAM_MANIFEST__ = read_raw_manifest_ssm(env_name, team_name)

    if "compute" in taskConfiguration and "profile" in taskConfiguration["compute"]:
        profile = __CURRENT_TEAM_MANIFEST__["compute"]["profile"]
        _logger.info(f"using profile %s", profile)
    else:
        profile = team_constants.default_profile()
        _logger.info(f"using default profile %s", profile)

    if profile and "image" in profile:
        image = profile["image"]
    else:
        repository = __CURRENT_TEAM_MANIFEST__["final-image-address"]
        image = f"{repository}:latest"

    node_type = get_node_type(taskConfiguration)

    job_name: str = f'run-{taskConfiguration["task_type"]}'
    job = _get_job_spec(
        job_name=job_name,
        team_name=team_name,
        cmds=["python", "/opt/python-utils/notebook_cli.py"],
        env_vars=env,
        image=image,
        node_type=node_type,
        labels=labels,
        team_constants=team_constants,
    )

    return job


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

    node_type = get_node_type(taskConfiguration)
    labels = {
        "app": f"orbit-runner",
        "orbit/node-type": node_type,
    }

    job_spec = _create_eks_job_spec(taskConfiguration, labels)

    if "AWS_WEB_IDENTITY_TOKEN_FILE" in os.environ and "eks.amazonaws.com" in os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"]:
        k8_config.load_incluster_config()
    else:
        k8_config.load_kube_config()

    _make_create_pvc_request(team_name=team_name, labels=labels)

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


def _run_task_ecs(taskConfiguration: dict) -> Any:
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
    _logger.debug(f"Execution Payload: {payload}")
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

    _logger.debug(f"Execution Response: {response_payload}")
    return response_payload


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
    elif taskConfiguration["compute_type"] == "ecs":
        return schedule_task_ecs(triggerName, frequency, taskConfiguration)
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
    elif taskConfiguration["compute_type"] == "ecs":
        return schedule_task_ecs(triggerName, frequency, taskConfiguration)
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

    labels = {"app": f"orbit-runner", "orbit/node-type": node_type}

    job_spec = _create_eks_job_spec(taskConfiguration, labels=labels)
    cron_job_template: V1beta1JobTemplateSpec = V1beta1JobTemplateSpec(spec=job_spec)
    cron_job_spec: V1beta1CronJobSpec = V1beta1CronJobSpec(job_template=cron_job_template, schedule=frequency)

    job = V1beta1CronJob(
        api_version="batch/v1beta1",
        kind="CronJob",
        metadata=V1ObjectMeta(name=f"orbit-{team_name}-{triggerName}", labels=labels, namespace=team_name),
        status=V1beta1CronJobStatus(),
        spec=cron_job_spec,
    )

    if "AWS_WEB_IDENTITY_TOKEN_FILE" in os.environ and "eks.amazonaws.com" in os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"]:
        k8_config.load_incluster_config()
    else:
        k8_config.load_kube_config()

    _make_create_pvc_request(team_name=team_name, labels=labels, request_timeout=120)

    job_instance: V1beta1CronJob = BatchV1beta1Api().create_namespaced_cron_job(namespace=team_name, body=job)

    metadata: V1ObjectMeta = job_instance.metadata
    return {
        "ExecutionType": "eks",
        "Identifier": metadata.name,
    }

    metadata: V1ObjectMeta = job_instance.metadata

    _logger.debug(f"started job {metadata.name}")


def delete_task_schedule(triggerName: str, compute_type: str = "eks") -> None:
    if compute_type == "eks":
        return delete_task_schedule_eks(triggerName)
    elif compute_type == "ecs":
        return delete_task_schedule_ecs(triggerName)
    else:
        raise RuntimeError("Unsupported compute_type '%s'", compute_type)


def delete_task_schedule_ecs(triggerName: str) -> None:
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
    props = get_properties()
    triggerName = f"orbit-{props['AWS_ORBIT_ENV']}-{props['AWS_ORBIT_TEAM_SPACE']}-{triggerName}"
    response = events_client.remove_targets(Rule=triggerName, Ids=["1"], Force=True)

    events_client.delete_rule(Name=triggerName, Force=True)
    print("notebook schedule deleted: ", triggerName)


def delete_task_schedule_eks(triggerName: str) -> None:
    props = get_properties()
    team_name = props["AWS_ORBIT_TEAM_SPACE"]
    if "AWS_WEB_IDENTITY_TOKEN_FILE" in os.environ and "eks.amazonaws.com" in os.environ["AWS_WEB_IDENTITY_TOKEN_FILE"]:
        k8_config.load_incluster_config()
    else:
        k8_config.load_kube_config()

    BatchV1beta1Api().delete_namespaced_cron_job(name=f"orbit-{team_name}-{triggerName}", namespace=team_name)


def schedule_task_ecs(triggerName: str, frequency: str, notebookConfiguration: dict) -> Any:
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
    props = get_properties()
    triggerName = f"orbit-{props['AWS_ORBIT_ENV']}-{props['AWS_ORBIT_TEAM_SPACE']}-{triggerName}"
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
        orbit_task = json.loads(vars["tasks"].replace("'", '"'))
        if "notebookName" in orbit_task["tasks"][0]:
            task_name = (
                orbit_task["tasks"][0]["notebookName"].split(".")[0] if "notebookName" in orbit_task["tasks"][0] else ""
            )
        elif "module" in orbit_task["tasks"][0]:
            module = orbit_task["tasks"][0]["module"]
            functionName = orbit_task["tasks"][0]["functionName"] if "functionName" in orbit_task["tasks"][0] else ""
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
    _logger.info("Waiting for %s tasks %s", len(tasks), tasks)

    while True:
        for task in tasks:
            _logger.debug("Checking execution state of: %s", task)
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
                _logger.info("waiting...")
                time.sleep(delay)


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
            if not pod_status.container_statuses:
                for c in pod_status.conditions:
                    condition: V1PodCondition = cast(V1PodCondition, c)
                    if condition.reason == "Unschedulable":
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


def wait_for_tasks_to_complete_ecs(
    tasks: List[Dict[str, str]],
    delay: Optional[int] = 60,
    maxAttempts: Optional[int] = 10,
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
    sfn = boto3.client("stepfunctions")
    logs = boto3.client("logs")

    props = get_properties()

    waiter_model = WaiterModel(get_stepfunctions_waiter_config(delay=delay, max_attempts=maxAttempts))
    waiter = waiter_model.get_waiter("ExecutionComplete")

    completed_tasks = []
    errored_tasks = []
    attempts = 0

    while True:
        incomplete_tasks = []
        attempts += 1

        while tasks:
            task = tasks.pop(0)
            _logger.debug(f"Checking execution state of: {task}")
            response = sfn.describe_execution(executionArn=task["ExecutionArn"])

            for acceptor in waiter.acceptors:
                if acceptor.matcher_func(response):
                    task["State"] = acceptor.state
                    if acceptor.state == "success":
                        _logger.debug("Execution success")
                        completed_tasks.append(task)
                        break
                    elif acceptor.state == "failure":
                        _logger.debug("Execution failure")
                        errored_tasks.append(task)
                        break
            else:
                if "Error" in response:
                    task["State"] = response["Error"].get("Message", "Unknown")
                    _logger.debug(f"Execution error: {task['State']}")
                    errored_tasks.append(task)
                else:
                    _logger.debug("Tasks are running...")
                    incomplete_tasks.append(task)

        tasks = incomplete_tasks

        _logger.info(f"Running: {len(tasks)} Completed: {len(completed_tasks)} Errored: {len(errored_tasks)}")

        if not tasks:
            _logger.info("All tasks stopped")
            break

        if attempts >= maxAttempts:
            _logger.info("Stopped waiting as maxAttempts reached")
            break

        time.sleep(delay)

    if tail_log:
        _logger.debug("Tailing Logs")

        def log_config(task):
            _logger.debug(f"Getting Log Config for Task: {task}")
            if task["ExecutionType"] == "ecs":
                id = task["Identifier"].split("/")[2]
                config = {
                    "Identifier": task["Identifier"],
                    "LogGroupName": f"/orbit/tasks/{props['AWS_ORBIT_ENV']}/{props['AWS_ORBIT_TEAM_SPACE']}/containers",
                    "LogStreamName": f"orbit-{props['AWS_ORBIT_ENV']}-{props['AWS_ORBIT_TEAM_SPACE']}/orbit-runner/{id}",
                }
                _logger.debug(f"Found LogConfig: {config}")
                return config
            elif task["ExecutionType"] == "eks":
                log_group = f"/orbit/pods/{props['AWS_ORBIT_ENV']}"
                prefix = f"fluent-bit-kube.var.log.containers.{task['Identifier']}-"
                response = logs.describe_log_streams(logGroupName=log_group, logStreamNamePrefix=prefix)
                log_streams = response.get("logStreams", [])
                if log_streams:
                    config = {
                        "Identifier": task["Identifier"],
                        "LogGroupName": log_group,
                        "LogStreamName": log_streams[0]["logStreamName"],
                    }
                    _logger.debug(f"Found LogConfig: {config}")
                    return config
                else:
                    _logger.debug("No LogConfig found")
                    return None
            else:
                _logger.debug("No LogConfig found")
                return None

        def print_logs(type, log_configs):
            if not log_configs:
                return

            print("-" * 20 + f" {type} " + "-" * 20)
            for log_config in log_configs:
                _logger.debug(f"Retrieving Logs for: {log_config}")
                if log_config is None:
                    continue

                print(f"Identifier: {log_config['Identifier']}")
                response = logs.get_log_events(
                    logGroupName=log_config["LogGroupName"],
                    logStreamName=log_config["LogStreamName"],
                    limit=20,
                )

                for e in response.get("events", []):
                    print(
                        datetime.fromtimestamp(e["timestamp"] / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                        e["message"],
                    )
                else:
                    print()

        print_logs("Completed", [log_config(t) for t in completed_tasks])
        print_logs("Errored", [log_config(t) for t in errored_tasks])
        print_logs("Running", [log_config(t) for t in tasks])


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
