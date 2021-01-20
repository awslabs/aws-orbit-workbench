import datetime
import json
import logging
import time
from typing import Any, Dict, List

import boto3

import aws_orbit_sdk.controller as controller
import aws_orbit_sdk.emr as sparkConnection
from aws_orbit_sdk.common import get_workspace

# Initialize parameters
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger()
glue = boto3.client("glue")
sns = boto3.client("sns")
s3 = boto3.client("s3")

# Adding output path and other parameters for the reports
notebook_name = "Automated-Data-Transformations.ipynb"
workspace = get_workspace()
team_space = workspace["team_space"]
env_name = workspace["env_name"]
source_path = "$ORBIT_TRANSFORMATION_NOTEBOOKS_ROOT"
base_path = "orbit/profiling"
logger.info(f"Team space: {team_space}, Environment name: {env_name}")


def create_tasks(
    glue_tables: List[str], target_folder: str, database: str, samplingRatio: float
) -> List[Dict[str, str]]:
    """
    Creating a data profiling task for each Glue table in the database.

    Parameters
    ------------
    glue_tables : list
        A list of Table Objects in the database from AWS Glue
    target_folder : str
        The location of the final reports and notebooks that are generated
    database : str
        The database in the catalog whose tables to list. For Hive compatibility, this name is entirely lowercase.
    samplingRatio : float
        The sample ratio of rows used for inferring (default: 0.05)

    Returns
    --------
    tasks : list
        A list of profiling tasks ready to be run.

    Example
    --------
    >>> import aws.utils.notebooks.transformations.transformations as transformations
    >>> response = glue.get_tables(
    ...                            DatabaseName=parameters['database'],
    ...                            Expression=parameters['table_filter']
    ...                           )
    >>> tasks = create_tasks(glue_tables= response,
    ...                      target_folder='dataprofiling',
    ...                      database='mydatabase',
    ...                      samplingRatio=0.05
    ...                     )
    """
    i = 0
    tasks = []
    for table in glue_tables["TableList"]:
        i = i + 1
        task = {
            "notebookName": notebook_name,
            "sourcePath": source_path,
            "targetPath": f"{base_path}/{target_folder}",
            "targetPrefix": "p{}".format(i),
            "params": {
                "database_name": database,
                "table_to_profile": table["Name"],
                "samplingRatio": samplingRatio,
            },
        }
        tasks.append(task)
    logger.debug(f"Tasks: {json.dumps(tasks, indent=4, sort_keys=True, default=str)}")
    return tasks


#
# Main profiling function
def data_profile(parameters: Dict[str, str]) -> Dict[str, Any]:
    """
    Runs a data profiling task and returns the profiling reports to a target folder in s3.

    Parameters
    ------------
    parameters : dict
        Dictionary of different optional and required parameters to run the data profiling task (listed below)

        cluster_name : str, optional
            A unique name for the EMR cluster (default: 'lake-user-TestCluster')
        reuse_cluster : bool, optional
            If reuse_cluster is True and cluster exists , will reuse the existing cluster (default: 'True')
        start_cluster : bool, optional
            If start_cluster is True and cannot re-use cluster, then will start a new cluster (default: 'True')
        show_container_log : bool, optional
            If True, will tail the log of the containers until they are stopped (default: False)
        core_instance_count : int, optional
            The number of the instances within the cluster (default: 4)
        samplingRatio : float, optional
            The sample ratio of rows used for inferring (default: 0.05)
        terminate_cluster : str, optional
            If terminate_cluster is False and cluster exists, will not terminate cluster (default: 'False')
        total_runtime : int
            The number of minutes allocated to the notebook to run
        sns_topic : str, optional
            A name for the topic that will get updates on the tasks execution
        database : str
            Database name to profile
        table_filter : str
            A string filter for the tables to profile, can be a single table
            (i.e 'de1_0_2008_beneficiary_summary_file_sample_1') or a regex expression (i.e 'de*' for all tables)
        target_folder : str
            The location of the final reports and notebooks that are generated
        container_concurrency : int, optional
            The number of containers that runs in parallel (default: 1)
        trigger_name : str, optional
            The name of the trigger function in case there is a scheduled task
        frequency : str, optional
            The frequency of the trigger function, cron-like i.e: "cron(0/3 * 1/1 * ? *)"

    Returns
    --------
    response : dict
        The response will be a dictionary that contains the table list and the target folder for the notebooks and
        reports

    Example
    --------
    >>> import aws.utils.notebooks.transformations.transformations as transformations
    >>> params = {
    ...            "total_runtime" : 1800,
    ...            "database" : "cms_raw_db",
    ...            "table_filter" : 'de1_0_2008_beneficiary_summary_file_sample_1',
    ...            "target_folder" : target_folder
    ...          }
    >>> response = transformations.data_profile(params)
    """

    # Initialize: Check if there are missing optional parameters
    if "reuse_cluster" not in parameters:
        parameters["reuse_cluster"] = "True"
    if "start_cluster" not in parameters:
        parameters["start_cluster"] = "True"
    if "cluster_name" not in parameters:
        parameters["cluster_name"] = "lake-user-TestCluster"
    if "terminate_cluster" not in parameters:
        parameters["terminate_cluster"] = "False"
    if "container_concurrency" not in parameters:
        parameters["container_concurrency"] = 1
    if "show_container_log" not in parameters:
        parameters["show_container_log"] = False
    if "core_instance_count" not in parameters:
        parameters["core_instance_count"] = 4
    if "samplingRatio" not in parameters:
        parameters["samplingRatio"] = 0.05

    # Start Spark
    logger.info(f"Starting Spark cluster")
    livy_url, cluster_id, started = sparkConnection.connect_to_spark(
        parameters["cluster_name"],
        reuseCluster=parameters["reuse_cluster"],
        startCluster=parameters["start_cluster"],
        clusterArgs={"CoreInstanceCount": parameters["core_instance_count"]},
    )
    logger.info(f"Cluster is ready:{livy_url} livy_url:{cluster_id} cluster_id: started:{started}")

    # Get profiling data and print pretty json
    response = glue.get_tables(DatabaseName=parameters["database"], Expression=parameters["table_filter"])
    logger.debug(f"Glue response: {json.dumps(response, indent=4, sort_keys=True, default=str)}")

    if len(response["TableList"]) == 0:
        assert False

    tasks = create_tasks(
        response,
        parameters["target_folder"],
        parameters["database"],
        parameters["samplingRatio"],
    )

    # Running the tasks
    logger.info(f"Starting to run spark tasks")
    notebooks_to_run = {
        "compute": {"container": {"p_concurrent": parameters["container_concurrency"]}},
        "tasks": tasks,
        "env_vars": [
            {"name": "cluster_name", "value": parameters["cluster_name"]},
            {"name": "start_cluster", "value": parameters["start_cluster"]},
            {"name": "reuse_cluster", "value": parameters["reuse_cluster"]},
            {"name": "terminate_cluster", "value": parameters["terminate_cluster"]},
        ],
    }

    # Append sns topic if given as parameter
    if "sns_topic" in parameters:
        notebooks_to_run["compute"]["sns.topic.name"] = parameters["sns_topic"]

    # Running the tasks on containers
    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)

    if "trigger_name" in parameters:
        if "frequency" not in parameters:
            raise Exception("Missing frequency parameter while a trigger_name was given")
        container = controller.schedule_notebooks(parameters["trigger_name"], parameters["frequency"], notebooks_to_run)
    else:
        container = controller.run_notebooks(notebooks_to_run)

    if isinstance(container, str):
        containers = [container]
    else:
        containers = []
        containers = containers + container

    logger.info(
        f"Task : {current_time}, {str(container)}, --> {notebooks_to_run['tasks'][0]['params']['table_to_profile']}"
    )

    logger.debug(f"Starting time: {datetime.datetime.now()}")
    controller.wait_for_tasks_to_complete(
        containers,
        120,
        int(parameters["total_runtime"] / 120),
        parameters["show_container_log"],
    )
    logger.debug(f"Ending time: {datetime.datetime.now()}")

    # Shutting down Spark cluster
    if started and parameters["terminate_cluster"] == "True":
        logger.info(f"Shutting down Spark cluster")
        sparkConnection.stop_cluster(cluster_id)

    logger.debug(f"data_profile results are in: {base_path}")

    # Returning the result path and tables that ran on
    tables = []
    for table in response["TableList"]:
        tables.append(table["Name"])
    res = {
        "tables": tables,
        "result_path": f"{base_path}/{parameters['target_folder']}",
    }

    return res
