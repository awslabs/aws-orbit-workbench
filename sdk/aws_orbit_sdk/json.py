import glob
import json
import logging
import os
import subprocess
from os.path import expanduser
from pathlib import Path
from tempfile import mkstemp
from typing import Any, Dict, List, Optional, Union

import boto3
import IPython.display
from IPython.display import JSON

from aws_orbit_sdk.common import get_properties, get_workspace, split_s3_path

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()


def display_json(doc: Dict[str, Any], root: Optional[str] = "root") -> IPython.core.display.JSON:
    """
    Create a JSON display object given raw JSON data.

    Parameters
    ----------
    doc : JSON dict or list
        Raw JSON data to display.
    root : str, optional
        The name of the root element of the JSON tree (default 'root').

    Returns
    -------
    IPython display of JSON data : IPython.core.display.JSON
        An IPython JSON display representing the data.

    Example
    -------
    >>> from aws.utils.notebooks import json  as json_utils
    >>> json_utils.display_json(doc=my_schemas ,root="database")
    """

    return JSON(doc)


def write_json(doc: Any, path: str) -> None:
    """
    Write data to a s3 bucket path.

    Parameters
    ----------
    doc : Any (Object Data)
        Data to write to a s3 bucket.

    path : str
        s3 Bucket path for where to write data.

    Returns
    -------
    None
        None.

    Example
    -------
    >>> from aws.utils.notebooks import json  as json_utils
    >>> data = {
    ...     'id' : [1]
    ...     'name': ['Noah']
    ...     }
    >>> write_json(doc=data, path='testbucket123')
    """

    s3 = boto3.client("s3")
    if path.startswith("s3://"):
        (bucket, key) = split_s3_path(path)
        s3.put_object(Body=doc, Bucket=bucket, Key=key)

    dir = os.path.dirname(path)
    Path(dir).mkdir(parents=True, exist_ok=True)

    with open(path, "w") as outfile:
        json.dump(doc, outfile)


def run_schema_induction(
    data_path: str,
    table_name: str,
    s3_location: str,
    root_definition_name: str,
    is_array: Optional[bool] = True,
) -> Dict[str, Dict[str, str]]:
    """
    Calls on helper functions to run Schema Induction with given user arguments and returns ddl and schema metadata.

    Parameters
    ----------
    data_path : str
        An input json file path.
    table_name : str
        Table name to use when creating DDL.
    s3_location : str
        Table location to use when creating DDL.
    root_definition_name : str
        The root directory name of the data.
    is_array : bool, optional
        Is the document a json array.

    Returns
    -------
    ddl : str
        SQL ddl statement to create new external table with given metadata
    schema : dict
        Schema metadata stored as a json for the specified table.

    Example
    -------
    >>> from aws.utils.notebooks import json  as json_utils
    >>>table = json_utils.run_schema_induction(data_path=f's3://{target_bucket}/Claim-1/data.json',
    ...              table_name='users.table',
    ...              s3_location=f's3://{target_bucket}/Claim-1/',
    ...              root_definition_name='Claim',
    ...              is_array=True)
    >>> json_utils.display_json(table['schema'])
    >>> ddl = table['ddl']
    """

    logger.info("Start induction process for " + table_name)

    args = [
        "-i",
        data_path,
        "-c",
        "ec2",
        "-t",
        table_name,
        "--location",
        s3_location,
        "--root",
        root_definition_name,
    ]
    if is_array:
        args.append("-a")

    ret = run_schema_induction_args(args)

    logger.info("Finish induction process for " + table_name)

    return ret


def run_process(args: Union[str, List[str]]) -> None:
    """
    Helper function called by run_schema_induction_args() to log outputs and errors.

    Parameters
    ----------
    args : Union[str, List[str]]
        User arguments used for the schema induction process to run.

    Returns
    -------
    None
        None.
    """
    try:
        completed = subprocess.run(
            args,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as err:
        logger.error(f"ERROR: {err}")
    else:
        out = completed.stdout.decode("utf-8")
        err = completed.stderr.decode("utf-8")
        if len(out) > 0:
            logger.info(out)
        if len(err):
            logger.error(err)


def run_schema_induction_args(user_args: Union[str, List[str]]) -> Dict[str, Dict[str, str]]:
    """
    Calls on run_process to run Schema Induction with given user arguments gets ddl and schema metadata for a specified
    table.

    Parameters
    ----------
    user_args : Union[str, List[str]]
        User parameters including ( data_path, instance type, table_name, s3_location, and root definition name)

    Returns
    -------
    ddl : str
        SQL ddl statement to create new external table with given metadata.
    schema :
        Schema metadata stored as a json for the specified table.


    Examples
    --------
    >>>from aws.utils.notebooks import json  as json_utils
    >>>args = [ "-i data_path -c ec2 -t table_name --location s3_location --root ClaimData"]
    >>>args.append("-a")
    >>>table = json_utils.run_schema_induction_args(args)
    """

    ddlFd, ddl_path = mkstemp()
    schemaFd, schema_path = mkstemp()

    home = expanduser("~")

    jar = glob.glob(f"{home}/orbit/java/schema-induction*.jar")[0]

    args = [
        "/opt/jdk-13.0.1/bin/java",
        "-jar",
        f"{jar}",
        "-s",
        schema_path,
        "-d",
        ddl_path,
    ]
    args.extend(user_args)

    run_process(args)

    ddl = readFile(ddl_path, ddlFd)
    schema = readFile(schema_path, schemaFd)

    return {"ddl": ddl, "schema": schema}


def readFile(path: str, fd: int) -> Any:
    """
    Read File Contents located at a specified path.

    Parameters
    ----------
    path : str
        File path to locate file to read.
    fd : int
        Associated file descriptor

    Returns
    -------
    content : Any
        File contents

    Example
    -------
    >>>from aws.utils.notebooks import json  as json_utils
    >>>path = "/home/ihritik/Desktop/file2.txt"
    >>>fd = os.open( "foo.txt", os.O_RDONLY)
    >>>data = json_utils.readFile(path=path,fd=fd)
    """

    file = open(path, "r")
    content = file.read()
    file.close()
    os.close(fd)
    os.remove(path)
    return content
