import json
import logging
import os
import socket
import time
from typing import Any, Dict, List, Mapping, Optional, Tuple

import boto3
import requests

from aws_orbit_sdk.common import *

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()

SSM_PARAMETER_PREFIX = "/emr_launch/emr_launch_functions"


def get_virtual_cluster_id() -> str:
    emr = boto3.client("emr-containers")
    props = get_properties()
    env_name = props["AWS_ORBIT_ENV"]
    team_space = props["AWS_ORBIT_TEAM_SPACE"]
    response = emr.list_virtual_clusters(
        containerProviderId=f"orbit-{env_name}", containerProviderType="EKS", states=["RUNNING"], maxResults=500
    )
    if "virtualClusters" not in response or len(response["virtualClusters"]) == 0:
        raise Exception("Virtual EMR Cluster not found")
    for c in response["virtualClusters"]:
        if c["name"] == f"orbit-{env_name}-{team_space}":
            return c["id"]


def stop_cluster(cluster_id: str) -> None:
    """
    Stops a running EMR cluster.

    Parameters
    ----------
    cluster_id : str
        The EMR cluster ID to terminate

    Returns
    -------
    None
        None.

    Example
    -------
    >>> import aws.utils.notebooks.spark.emr as sparkConnection
    >>> sparkConnection.stop_cluster(cluster_id=cluster_id)
    """

    emr = boto3.client("emr")

    response = emr.terminate_job_flows(JobFlowIds=[cluster_id])
    logger.info("stopping cluster %s", cluster_id)
    logger.info(response)
    return None


def connect_to_spark(
    cluster_name: Optional[str] = None,
    reuseCluster: Optional[bool] = True,
    startCluster: Optional[bool] = False,
    clusterArgs: Optional[Dict[str, str]] = dict(),
    waitWhenResizing: Optional[bool] = True,
) -> Tuple[str, str, bool]:
    """
    Returns a livy URL that can be used to start a new spark session. The API can also create a new cluster if it does
    not exists.

    Parameters
    ----------
    cluster_name : str, optional
        A unique name for the EMR cluster
    reuseCluster : string, optional
        If reuseCluster is True and cluster exists , will reuse the existing cluster (default: True)
    startCluster : string, optional
        If startCluster is True and cannot re-use cluster, then will start a new cluster (default: False)
    clusterArgs : dict, optional
        Optional list of arguments to control the EMR definition used to start the new cluster
    waitWhenResizing : bool, optional
        If waitWhenResizing is True and the cluster task nodes are resizing, the call will wait until operation is completed

    Returns
    -------
    livy_url : str
        The livy url to use for starting the spark session
    cluster_id : str
        The EMR cluster ID used in the session
    started : bool
        True if a new cluster was started in this call

    Example
    -------
    >>> import aws.utils.notebooks.spark.emr as sparkConnection
    >>> import sparkmagic.utils.configuration as conf
    >>> conf.override(conf.livy_session_startup_timeout_seconds.__name__, 240)
    >>> (livy_url, cluster_id, started) = sparkConnection.connect_to_spark(clusterName=clusterName,
    ...                                                            reuseCluster=True,
    ...                                                            startCluster=True,
    ...                                                            clusterArgs={},
    ...                                                            waitWhenResizing=True)
    """
    props = get_properties()
    if cluster_name == None:
        if "ClusterName" in clusterArgs:
            cluster_name = clusterArgs["ClusterName"]

    emr = boto3.client("emr")
    ClusterStates = ["STARTING", "BOOTSTRAPPING", "RUNNING", "WAITING"]
    res = emr.list_clusters(ClusterStates=ClusterStates)
    while True:
        clusters = res["Clusters"]
        # choose the correct cluster
        clusters = [c for c in clusters if c["Name"] == cluster_name]
        if clusters:
            break
        elif not "Marker" in res.keys():
            break
        else:
            res = emr.list_clusters(Marker=res["Marker"], ClusterStates=ClusterStates)

    cluster_id = ""
    started = False
    if reuseCluster:
        if not clusters:
            if not startCluster:
                raise Exception("cannot find running EMR cluster: " + cluster_name)
            else:
                (master_ip, cluster_id) = _start_and_wait_for_emr(emr, cluster_name, props, clusterArgs)
                started = True
        else:
            cluster_id = clusters[0]["Id"]
            # possibly the cluster exists but is in the middle of resizing
            _wait_for_cluster_groups(emr, cluster_id)
            master_ip = _get_cluster_ip(emr, cluster_id)

    else:
        if not startCluster:
            raise Exception("If reuseCluster is False , then startCluster must be True")
        else:
            (master_ip, cluster_id) = _start_and_wait_for_emr(emr, cluster_name, props, clusterArgs)
            started = True

    if waitWhenResizing:
        _wait_for_cluster_groups(emr, cluster_id)

    # conn_template = "-s spark -c spark -l python -u http://{}:8998 -t None ADD"
    conn_template = "http://{}:8998"
    conn = conn_template.format(master_ip)

    return (conn, cluster_id, started)


def getSparkSessionInfo(livyUrl: str, appID: str) -> Dict[str, Any]:
    """
    Returns spark session info for each session created (e.g. id, name, owner, appInfo, log, etc.)

    Parameters
    ----------
    livyUrl : str
        The livy url to connect to the spark session.
    appID : str
        The application id of this session.

    Returns
    -------
    sessionInfo : Dict[str, Any]
        JSON formatted data about the spark session.

    Example
    -------
    >>> import aws.utils.notebooks.spark.emr as sparkConnection
    >>> (livy_url, cluster_id, started) = sparkConnection.connect_to_spark(clusterName = "test1",
    ...                                                                    reuseCluster=True,
    ...                                                                    startCluster=True,
    ...                                                                    clusterArgs={})
    >>> appID = spark.sparkContext.applicationId
    >>> getSparkSessionInfo(livyUrl = livy_url, appID = appID)
    """
    sessionInfo = livyUrl + "/sessions"
    r_params = {}
    r = requests.get(url=sessionInfo, params=r_params).json()
    print("session count:" + str(r["total"]))
    sessions = [s for s in r["sessions"] if s["appId"] == appID]
    if len(sessions) > 0:
        return next(sessions)
    else:
        return None


def _get_cluster_id(emr: boto3.client("emr"), clusterName: str) -> str:
    """
    Returns the id of a running cluster with given cluster name.
    """
    clusters = emr.list_clusters()["Clusters"]

    # choose the correct cluster
    clusters = [c for c in clusters if c["Name"] == clusterName and c["Status"]["State"] in ["WAITING", "RUNNING"]]
    if not clusters:
        logger.info("No valid clusters")
        raise Exception("cannot find running cluster: " + clusterName)
    # take the first relevant cluster
    return clusters[0]["Id"]


def _get_cluster_ip(emr: boto3.client("emr"), cluster_id: str, wait_ready: Optional[bool] = True) -> str:
    """
    Waits for instances to be running and then returns the private ip address from the cluster master node.
    """
    if wait_ready:
        _wait_for_cluster_groups(emr, cluster_id)

    response = emr.list_instances(
        ClusterId=cluster_id,
        InstanceGroupTypes=[
            "MASTER",
        ],
    )
    for instance in response["Instances"]:
        if instance["Status"]["State"] == "RUNNING":
            return instance["PrivateIpAddress"]

    if not wait_ready:
        return "not ready"

    raise Exception("Master node is not available: " + str(response["Instances"]))


def get_emr_step_function_error(execution_arn: str) -> None:
    """
    Looks at execution history and gets tries to output error message for EMR cluster's failed start (automatically
    called if EMR fails to start).

    Parameters
    ----------
    execution_arn : str
        The Amazon Resource Name (ARN) of the execution.

    Returns
    -------
    None
        None.
    """
    sfn = boto3.client("stepfunctions")
    logger.error(f"Step function failed launching EMR, execution_arn: {execution_arn}")
    response = sfn.get_execution_history(
        executionArn=execution_arn,
    )
    try:
        state = json.loads(response["events"][len(response["events"]) - 2]["stateEnteredEventDetails"]["input"])
        error = json.loads(state["Error"]["Cause"])
        logger.error(error["errorMessage"])
        raise Exception(error["errorMessage"])
    except:
        logger.error(json.dumps(response))
        raise Exception("Cluster failed starting")


def _start_and_wait_for_emr(
    emr: boto3.client("emr"),
    cluster_name: str,
    props: Dict[str, str],
    clusterArgs: Optional[Dict[str, str]] = dict(),
    wait_ready: Optional[bool] = True,
) -> Tuple[str, str]:
    """
    Start EMR and wait for cluster to begin running as well as get any execution errors.
    """
    sfn = boto3.client("stepfunctions")
    logger.info(f"entering _start_and_wait_for_emr() {cluster_name}")

    emr_functions = _get_emr_functions()
    if len(emr_functions) == 0:
        raise Exception("cannot find any EMR launch functions for this team space")

    if "emr_start_function" in clusterArgs.keys():
        emr_function = emr_functions[clusterArgs["emr_start_function"]]
        del clusterArgs["emr_start_function"]
    else:
        emr_function = list(emr_functions.values())[0]

    clusterArgs["ClusterName"] = cluster_name
    emr_input = {"ClusterConfigOverrides": clusterArgs}
    logger.info("Started EMR with {emr_function} and parameters: %s", emr_input)

    response = sfn.start_execution(stateMachineArn=emr_function["StateMachine"], input=json.dumps(emr_input))
    logger.debug(f"Started EMR step function {response}")

    while True:
        time.sleep(20)
        des_res = sfn.describe_execution(executionArn=response["executionArn"])
        logger.info(f"waiting for EMR to start...")
        if not wait_ready:
            return ("", "")
        if des_res["status"] != "RUNNING":
            break

    logger.info(f"Finished EMR step function")

    if (des_res["status"]) != "SUCCEEDED":
        get_emr_step_function_error(response["executionArn"])

    cluster = json.loads(des_res["output"])
    if "LaunchClusterResult" not in cluster:
        get_emr_step_function_error(response["executionArn"])

    cluster_id = cluster["LaunchClusterResult"]["ClusterId"]

    master_ip = _get_cluster_ip(emr, cluster_id, wait_ready)

    logger.info("cluster ready: %s  ip: %s ", cluster_id, master_ip)

    return (master_ip, cluster_id)


def _get_functions(namespace: Optional[str] = "default", next_token: Optional[str] = None) -> Mapping[str, Any]:
    """
    Returns an EMR Launch Function with its parameters and a next token if more functions exist for a given namespace.
    """
    params = {"Path": f"{SSM_PARAMETER_PREFIX}/{namespace}/"}
    if next_token:
        params["NextToken"] = next_token
    result = boto3.client("ssm").get_parameters_by_path(**params)

    functions = {"EMRLaunchFunctions": [json.loads(p["Value"]) for p in result["Parameters"]]}
    if "NextToken" in result:
        functions["NextToken"] = result["NextToken"]
    return functions


def get_emr_functions() -> List[str]:
    """
    Gets a list of EMR launch functions.

    Parameters
    ----------
    None
        None.

    Returns
    -------
    functions : list
        A list of EMR Launch functions

    Example
    -------
    >>> import aws.utils.notebooks.spark.emr as sparkConnection
    >>> funcs = sparkConnection.get_emr_functions()
    >>> funcs = list(funcs)
    >>> funcs
    """
    return list(_get_emr_functions().keys())


def describe_emr_function(funcName: str) -> Dict[str, Any]:
    """
    Get the EMR Launch Function parameters and values for a given function name.

    Parameters
    ----------
    funcName : str
        Name of the launch function you want information from.

    Returns
    -------
    emr_func : dict
        key-value pairs of different function parameter values.

    Example
    -------
    >>> %%local
    >>> import aws.utils.notebooks.spark.emr as sparkConnection
    >>> emr_func_name = 'standard-default'
    >>> emr_func = sparkConnection.describe_emr_function(emr_func_name)
    >>> emr_func['AllowedClusterConfigOverrides']
    """
    return _get_emr_functions()[funcName]


def _get_emr_functions() -> List[str]:
    """
    Returns a list of all EMR Launch functions and their current values.
    """
    props = get_properties()
    env_name = props["AWS_ORBIT_ENV"]
    team_space = props["AWS_ORBIT_TEAM_SPACE"]
    namespace = f"orbit-{env_name}-{team_space}"
    res = _get_functions(namespace)
    functionList = _get_functions(namespace=namespace)["EMRLaunchFunctions"]
    while "NextToken" in res:
        temp = _get_functions(res["NextToken"])["EMRLaunchFunctions"]
        functionList.extend(temp)

    func = dict()
    for f in functionList:
        func[f["LaunchFunctionName"]] = f

    return func


def _wait_for_cluster_groups(emr: boto3.client("emr"), cluster_id: str) -> None:
    """
    Waits for instance groups in cluster to start running.
    """
    attempts = 30
    while attempts > 0:
        attempts -= 1
        response = emr.list_instance_groups(ClusterId=cluster_id)
        wait = False
        for g in response["InstanceGroups"]:
            if g["Status"]["State"] in (
                "PROVISIONING",
                "BOOTSTRAPPING",
                "RECONFIGURING",
                "RESIZING",
            ):
                logger.info("waiting for cluster group: %s(%s)", g["Name"], g["Status"]["State"])
                wait = True
        if wait:
            time.sleep(30)
        else:
            break


def get_cluster_info(cluster_id: str) -> Dict[str, Dict[str, str]]:
    """
    Gets info on the Master, Core, and Task Nodes for an EMR Cluster.

    Parameters
    ----------
    cluster_id : str
        The EMR cluster ID used in the session

    Returns
    -------
    info : dict
        A dictionary object with information on the master, core, and task nodes existing in a specified cluster.

    Example
    -------
    >>> import aws.utils.notebooks.spark.emr as sparkConnection
    >>> get_cluster_info(cluster_id)
    """
    emr = boto3.client("emr")
    info = {}
    info["MASTER"] = emr.list_instances(ClusterId=cluster_id, InstanceGroupTypes=["MASTER"])
    info["CORE"] = emr.list_instances(ClusterId=cluster_id, InstanceGroupTypes=["CORE"])
    info["TASK"] = emr.list_instances(ClusterId=cluster_id, InstanceGroupTypes=["TASK"])

    return info


def spark_submit(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    This code will run your PySpark job on the spark EMR using your current source directory.

    Parameters
    ----------
    job : dict
        A pyspark job definition to execute

        cluster_id : str
            The EMR cluster ID
        app_name : str
            The Spark application Name
        module : str
            A relative path from repository root to the Python module containing the pyspark application
        waitAppCompletion : bool
            If True , will wait until EMR step is completed.
        app_args : list
            List of arguments to pass to the spark application
        spark_args : list
            List of arguments controlling the spark execution

    Returns
    -------
    response : dict
        The output for the AddJobFlowSteps operation and identifiers of the list of steps added to the job flow.

    Example
    -------
    >>> import aws.utils.notebooks.spark.emr as sparkConnection
    >>> response = sparkConnection.spark_submit(job = {
    ...                                         "cluster_id" : cluster_id,
    ...                                            "app_name":  "test1",
    ...                                            "module" : "samples/python/pyspark/createTbl.py",
    ...                                            "wait_app_completion": False,
    ...                                            "app_args": [arg1,arg2],
    ...                                            "spark_args": [--num-executors,2,--num_cores,4,--executor_memory,1g]
    ...                                             })
    """
    cluster_id = job["cluster_id"] if "cluster_id" in job.keys() else None
    if cluster_id == None:
        raise Exception("cluster_id must be provided")
    app_name = job["app_name"] if "app_name" in job.keys() else None
    if app_name == None:
        raise Exception("app_name must be provided")
    module = job["module"] if "module" in job.keys() else None
    if module == None:
        raise Exception("module must be provided")

    waitAppCompletion = job["wait_app_completion"] if "wait_app_completion" in job.keys() else False
    appargs = job["app_args"] if "app_args" in job.keys() else []
    sparkargs = job["spark_args"] if "spark_args" in job.keys() else []
    props = get_properties()
    if waitAppCompletion:
        waitApp = "true"
    else:
        waitApp = "false"

    workspaceDir = "workspace"

    notebookInstanceName = socket.gethostname()

    s3WorkspaceDir = "s3://{}/{}/workspaces/{}".format(
        props["AWS_ORBIT_S3_BUCKET"],
        props["AWS_ORBIT_TEAM_SPACE"],
        notebookInstanceName,
    )
    cmd = 'aws s3 sync --delete --exclude "*.git/*" {} {}'.format(workspaceDir, s3WorkspaceDir)
    logout = os.popen(cmd).read()
    logger.info("s3 workspace directory is %s", s3WorkspaceDir)
    logger.debug(logout)

    module = os.path.join(s3WorkspaceDir, module)

    emr = boto3.client("emr")
    args = [
        "/usr/bin/spark-submit",
        "--verbose",
        "--deploy-mode",
        "cluster",
        "--master",
        "yarn",
        "--conf",
        "pyspark.yarn.submit.waitAppCompletion=" + waitApp,
        "--conf",
        "hive.metastore.client.factory.class=com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory",
        "--conf",
        "hive.metastore.connect.retries=5",
    ]
    args.extend(sparkargs)
    args.append(module)
    args.extend(appargs)

    response = emr.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": app_name,
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {"Jar": "command-runner.jar", "Args": args},
            },
        ],
    )

    return response


def get_team_clusters(cluster_id: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """
    Finds all running clusters for a user' team space and returns cluster-level details including status, hardware
    and software configuration, VPC settings, and so on for each cluster.

    Parameters
    ----------
    cluster_id : str, optional
        The unique EMR cluster ID to get information about.

    Returns
    -------
    clusters_info : dict
        A dictionary of one or many clusters and their configuration.

    Example
    -------
    >>> import aws.utils.notebooks.spark.emr as sparkConnection
    >>> sparkConnection.get_team_clusters()
    """

    emr = boto3.client("emr")
    props = get_properties()
    if cluster_id == None:
        clusters = emr.list_clusters(ClusterStates=["STARTING", "BOOTSTRAPPING", "RUNNING", "WAITING"])
        if "Clusters" not in clusters:
            raise Exception("Error calling list_clusters()")
        if len(clusters["Clusters"]) == 0:
            logger.info("no emr clusters found for team space")
            return {}
        clusters = clusters["Clusters"]
    else:
        clusters = [{"Id": cluster_id}]

    clusters_info = {}
    for cluster in clusters:
        cluster_id = cluster["Id"]
        cluster_info = emr.describe_cluster(ClusterId=cluster_id)
        if "Cluster" not in cluster_info:
            raise Exception("Error calling describe_cluster()")

        tag_list = cluster_info["Cluster"]["Tags"]
        tags = {}
        for tag in tag_list:
            tags[tag["Key"]] = tag["Value"]

        if ORBIT_PRODUCT_KEY not in tags or tags[ORBIT_PRODUCT_KEY] != ORBIT_PRODUCT_NAME:
            continue

        if tags[ORBIT_ENV] != props["AWS_ORBIT_ENV"] or tags[AWS_ORBIT_TEAM_SPACE] != props["AWS_ORBIT_TEAM_SPACE"]:
            continue

        cluster_nodes_info = get_cluster_info(cluster_id)
        ip = _get_cluster_ip(emr, cluster_id, False)
        livy_url = f"http://{ip}:8998"
        cluster_model = {}
        cluster_model["cluster_id"] = cluster_id
        cluster_model["livy_url"] = livy_url
        cluster_model["ip"] = ip
        cluster_model["Name"] = cluster["Name"]
        cluster_model["State"] = cluster["Status"]["State"]
        cluster_model["info"] = cluster_info
        cluster_model["dashboard_link"] = "http://tbd"
        cluster_model["instances"] = cluster_nodes_info
        clusters_info[cluster_id] = cluster_model

    return clusters_info
