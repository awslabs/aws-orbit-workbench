import json
import logging
import time
from typing import Any, Dict, List, Optional

import boto3

from aws_orbit_sdk.common import get_workspace

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()


def delete_crawler(crawler: str) -> None:
    """
    Deletes a glue crawler.

    Parameters
    ----------
    crawler: str
        A unique name of the Crawler

    Returns
    -------
    None
        None.

    Example
    -------
    >>> import aws_orbit_sdk.glue_catalog as glue
    >>> delete_crawler(crawler= "crawler-name")
    """
    glue = boto3.client("glue")
    glue.delete_crawler(Name=crawler)
    logger.info("existing crawler deleted")


def run_crawler(crawler: str, target_db: str, target_path: str, wait: Optional[Any] = True) -> str:
    """
    This API starts a glue crawler for the given path and will create the tables base on data found in the provided
    database. The call can wait until the crawler is done and table created.

    Parameters
    ----------
    crawler: str
        A unique name of the Crawler
    target_db: str
        The name of the target database
    target_path: str
        The S3 Path where the data for the table resides.
    wait: optional, bool
        If True, will wait until the Crawler is finished.

    Returns
    -------
    state: str
        Returns the state of the crawler after finished running and creating tables.
    Example
    -------
    >>> import aws_orbit_sdk.glue_catalog as glue
    >>> response = glue.run_crawler(crawler, target_db, target_path, wait=True)
    """
    role = get_workspace()["EksPodRoleArn"]
    glue = boto3.client("glue")
    try:
        glue.delete_crawler(Name=crawler)
        logger.info("existing crawler deleted")
    except Exception as e:
        error = str(e)
        if "EntityNotFoundException" not in error:
            logger.error(error)
        pass

    response = glue.create_crawler(
        Name=crawler,
        Role=role,
        DatabaseName=target_db,
        Targets={"S3Targets": [{"Path": target_path}]},
    )
    state = response["ResponseMetadata"]["HTTPStatusCode"]
    if state != 200:
        raise Exception("Failed to create crawler")

    glue.start_crawler(Name=crawler)

    logger.info("Crawler started...")
    state = "INIT"
    while state != "READY":
        response = glue.get_crawler(Name=crawler)
        state = response["Crawler"]["State"]
        if not wait:
            return state
        logger.info(f"Crawler in state: {state}, waiting a min... ")
        time.sleep(60)

    response = glue.get_crawler_metrics(CrawlerNameList=[crawler])
    if "CrawlerMetricsList" not in response or "TablesCreated" not in response["CrawlerMetricsList"][0]:
        raise Exception("Crawler failed to create table")

    stats = response["CrawlerMetricsList"][0]

    logger.info(stats)

    logger.info("Crawler finished creating table")
    return state


def update_teamspace_lakeformation_permissions(db_name: Optional[str] = "*") -> None:
    """
    This call will perform a scan over the provided database's tables. Base on the security selector for the given
    Team Space and base on the current column tags, the permissions will be update to allow access for permitted
    columns.

    Parameters
    -----------
    db_name: optional, str
        Name of the database for which to update permissions.

    Returns
    -------
    None
        None.

    Example
    --------
    >>> import aws_orbit_sdk.glue_catalog as glue
    >>> glue.update_teamspace_lakeformation_permissions(database_name)
    """
    workspace = get_workspace()
    lambda_client = boto3.client("lambda")

    inp = {
        "env_name": workspace["env_name"],
        "team_space": workspace["team_space"],
        "db_name": db_name,
        "role_arn": workspace["EksPodRoleArn"],
    }
    payload = json.dumps(inp)
    response = lambda_client.invoke(
        FunctionName=f"orbit-{workspace['env_name']}-authorize_lake_formation_for_role",
        InvocationType="RequestResponse",
        LogType="Tail",
        Payload=bytes(payload, "utf-8"),
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        response_payload = json.loads(response["Payload"].read().decode("utf-8"))
        if "errorMessage" in response_payload:
            raise Exception(response_payload["errorMessage"])

    print("Lakeformation permissions have been updated")


def _update_column_parameters(table: Dict[str, Any], name: str, key: str, value: Optional[Any] = None) -> None:
    """
    Updates the column parameters of a given table.
    """
    columns = table["StorageDescriptor"]["Columns"]
    for c in columns:
        if c["Name"] == name:
            if value != None:
                if "Parameters" not in c:
                    c["Parameters"] = {}

                c["Parameters"][key] = value
            else:
                if "Parameters" in c and key in c["Parameters"]:
                    del c["Parameters"][key]


def tag_columns(
    database: str,
    table_name: str,
    key: str,
    table_tag_value: str,
    columns: Optional[List[str]] = None,
    column_tag_value: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update the tag values for a specific table or set of columns to increase or decrease security permissions.

    Parameters
    ----------
    database: str
        Name of the database
    table_name: str
        Name of the table on which to perform the tags
    key: required, str
        Tag key
    table_tag_value: str
        Tag value to give to the entire table.
    columns: list, optional
        List of columns to update with a column tag.
    column_tag_value: str, optional
        Tag value to give to the list of columns specified in the table

    Returns
    -------
    update_table: dict
        Dictionary containing the table object metadata and new tag values.

    Examples
    --------
    >>> import aws_orbit_sdk.glue_catalog as glue
    >>> update_table = orbit_catalog_api.tag_columns(
    ...                        database='secured_database',
    ...                        table_name='table1',
    ...                        key='security-level',
    ...                        table_tag_value='sec-4')
    """
    glue = boto3.client("glue")
    response = glue.get_table(DatabaseName=database, Name=table_name)
    update_table = response["Table"]
    if "Parameters" not in update_table["StorageDescriptor"]:
        update_table["StorageDescriptor"]["Parameters"] = {}

    update_table["StorageDescriptor"]["Parameters"][key] = table_tag_value

    if "DatabaseName" in update_table:
        del update_table["DatabaseName"]
    if "CreateTime" in update_table:
        del update_table["CreateTime"]
    if "UpdateTime" in update_table:
        del update_table["UpdateTime"]
    if "CreatedBy" in update_table:
        del update_table["CreatedBy"]
    if "IsRegisteredWithLakeFormation" in update_table:
        del update_table["IsRegisteredWithLakeFormation"]
    if columns != None:
        for c in columns:
            _update_column_parameters(update_table, c, key, column_tag_value)
    glue.update_table(DatabaseName=database, TableInput=update_table)
    return update_table


def untag_columns(
    database: str,
    table_name: Optional[str] = None,
    columns: Optional[List[str]] = None,
    key: Optional[str] = None,
    table_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Removes tags from a specified column or table, or all the tables in a given database.

    Note
    ----
    If a tag value is specified, the tag key gets updated to the ne tag value instead of the key being deleted.

    Parameter
    ---------
    database: str
        Name of the database
    table_name: str
        Name of the table on which to untag if specified
    columns: list
        List of columns to untag if specified
    key: str
        Tag key to remove
    table_tag: str
        Tag value to give to the entire table.

    Return
    ------
    update_table: dict
        Dictionary containing the table object metadata after being untagged.

    Example
    -------
    >>> import aws_orbit_sdk.glue_catalog as glue
    >>> orbit_catalog_api.untag_columns(database='secured_database',key='security-level')
    """
    glue = boto3.client("glue")
    table_names = []
    if table_name != None:
        table_names = [table_name]
    else:
        tables = glue.get_tables(DatabaseName=database)["TableList"]

        for table in tables:
            table_names.append(table["Name"])

    update_table = {}
    for table_name in table_names:
        response = glue.get_table(DatabaseName=database, Name=table_name)
        update_table = response["Table"]
        if "Parameters" not in update_table["StorageDescriptor"]:
            update_table["StorageDescriptor"]["Parameters"] = {}

        if table_tag != None:
            update_table["StorageDescriptor"]["Parameters"][key] = table_tag
        else:
            if key in update_table["StorageDescriptor"]["Parameters"]:
                del update_table["StorageDescriptor"]["Parameters"][key]

        if "DatabaseName" in update_table:
            del update_table["DatabaseName"]
        if "CreateTime" in update_table:
            del update_table["CreateTime"]
        if "UpdateTime" in update_table:
            del update_table["UpdateTime"]
        if "CreatedBy" in update_table:
            del update_table["CreatedBy"]
        if "IsRegisteredWithLakeFormation" in update_table:
            del update_table["IsRegisteredWithLakeFormation"]

        if columns == None:
            cols = table["StorageDescriptor"]["Columns"]
            columns = []
            for c in cols:
                columns.append(c["Name"])

        for c in columns:
            _update_column_parameters(update_table, c, key)

        logger.info(f"untagging table {table_name}")
        glue.update_table(DatabaseName=database, TableInput=update_table)
    return update_table


def getCatalogAsDict(database: Optional[str] = None) -> Dict:
    """
    Get Data Catalog of a specific Database

    Parameters
    ----------
    database : str
        Name of database to catalog.

    Returns
    -------
     schema : IPython.core.display.JSON
        An IPython JSON display representing the schema metadata for a database

    Example
    --------
    >>> from aws.utils.notebooks.database import AthenaUtils
    >>> from aws.utils.notebooks.json import display_json
    >>> AthenaUtils.getCatalog(database="my_database")
    """
    glue = boto3.client("glue")
    schemas: List[Dict[str, Any]] = []
    response = glue.get_databases()
    key: int = 0
    for db in response["DatabaseList"]:
        key += 1
        database = {"title": db["Name"], "key": str(key), "qname": db["Name"], "children": [], "_class": "database"}
        schemas.append(database)
        response = glue.get_tables(DatabaseName=db["Name"], MaxResults=50)
        for t in response["TableList"]:
            key += 1
            table = dict()
            table["title"] = t["Name"]
            table["key"] = str(key)
            table["location"] = (
                t["StorageDescriptor"]["Location"]
                if ("StorageDescriptor" in t and "Location" in t["StorageDescriptor"])
                else ""
            )
            table["children"] = []
            table["key"] = str(key)
            table["_class"] = "table"
            table["db"] = db["Name"]
            table["table"] = t["Name"]
            database["children"].append(table)
            for c in t["StorageDescriptor"]["Columns"]:
                col = dict()
                key += 1
                table["children"].append(col)
                col["title"] = c["Name"]
                col["type"] = c["Type"]
                col["key"] = str(key)
                col["_class"] = "column"
                col["db"] = db["Name"]
                col["table"] = t["Name"]
    return schemas
