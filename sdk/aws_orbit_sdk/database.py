"""Database Module. Redshift and Athena functionalities"""

import json
import logging
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import quote_plus

import boto3
import IPython.core.display
import pandas as pd
import pyathena
import sqlalchemy as sa
from IPython import get_ipython
from IPython.display import JSON
from pandas import DataFrame
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker

from aws_orbit_sdk.common import *
from aws_orbit_sdk.glue_catalog import run_crawler
from aws_orbit_sdk.json import display_json
from aws_orbit_sdk.magics.database import AthenaMagics, RedshiftMagics

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()

global __redshift__
global __athena__
__redshift__ = None
__athena__ = None


def check_in_jupyter():
    try:
        get_ipython()
        return True
    except NameError:
        return False


def get_redshift():
    global __redshift__
    if __redshift__ == None:
        __redshift__ = RedshiftUtils()
        if check_in_jupyter():
            ip = get_ipython()
            magics = RedshiftMagics(ip, __redshift__)
            ip.register_magics(magics)

    return __redshift__


def get_athena():
    global __athena__
    if __athena__ == None:
        __athena__ = AthenaUtils()
        if check_in_jupyter():
            ip = get_ipython()
            magics = AthenaMagics(ip, __athena__)
            ip.register_magics(magics)
    return __athena__


class DatabaseCommon:
    """
    Database functions, inherited by both Redshift and Athena classes.

    ...

    Attributes
    ----------
    current_engine : sqlalchemy.engine.Engine, optional

        A sql alchemy engine (default None).
    db_url : str, optional
        A sql alchemy connection string to a database (default None).
    redshift_role : str, optional
        The redshift role ARN that can be used to connect to Glue catalog (default None).
    db_class : str, optional
        The database class (default is None and is set when connecting to either Athena or Redshift).


    Methods
    -------
    def execute_ddl(self, ddl: str, namespace: Optional[Dict[str, str]] = dict()) -> None
        Executes a SQL ddl statement.

    def execute_query(self, sql: str, namespace: Optional[Dict[str, str]] = dict()) -> ResultProxy:
        Executes a SQL query.
    """

    current_engine = None
    db_url = None
    redshift_role = None
    db_class = None

    def execute_ddl(self, ddl: str, namespace: Optional[Dict[str, str]] = dict()) -> None:
        """
        Executes a SQL ddl statement.

        Parameters
        ----------
        ddl : str
            The data descrption language statement to execute in SQL.

        namespace : dict(), optional
            Mapping namespace keys to values if the values do not already exist.

        Returns
        -------
        None
            None.

        Examples
        --------
        >>> from aws.utils.notebooks.database import get_redshift
        >>> db_utils = get_redshift()
        >>> tableName = "myQuery1"
        >>> db_utils.execute_ddl(f'drop table if exists "mydatabase."{table_name}"')
        """

        with self.current_engine.connect() as conn:
            session = sessionmaker(bind=self.current_engine)()
            session.connection().connection.set_isolation_level(0)
            session.execute(ddl, namespace)
            conn.close()

    def execute_query(self, sql: str, namespace: Optional[Dict[str, str]] = dict()) -> sa.engine.result.ResultProxy:
        """
        Executes a SQL query.

        Parameters
        ----------
        sql : str
            SQL DML query.

        namespace : dict(), optional
            Mapping namespace keys to values if the values do not already exist.

        Returns
        -------
        rs : sqlalchemy.engine.result.ResultProxy
            Resulting data from sql query execution.

        Examples
        --------
        >>> from aws.utils.notebooks.database import get_redshift
        >>> db_utils = get_redshift()
        >>> db_utils.execute_query("select username from mydatabase.users")
        """

        with self.current_engine.connect() as conn:
            rs = self.current_engine.execute(sql, namespace)
            conn.close()
        return rs


class RedshiftUtils(DatabaseCommon):
    """
    Collection of Redshift functions used to easily connect and work with databases.

    Methods
    -------
    get_connection_to_redshift(self, clusterIdentifier, DbName, DbUser, lambdaName=None):
        Connect to an existing cluster or create a new cluster if it does not exists.

    create_external_schema(self, schema_name, glue_database)
         Creates external schema if it does not already exist from a glue data catalog database.

    create_external_table(self, select, database_name, table_name, format="Parquet", s3_location=None, options=""):
        Creates a new external table in the given database and runs a glue crawler to populate glue catalog tables with
        table metadata.

    connect_to_redshift(self, cluster_name, reuseCluster=True, startCluster=False, clusterArgs=dict()):
        Connects to a Redshift Cluster and returns connection information once redshift cluster is available for use.

    delete_redshift_cluster(self, cluster_name):
        Deletes a redshift cluster.

    get_redshift_functions(self):
        Provides a list of Redshift Functions that can be used.

    describe_redshift_function(self, funcName):
        Returns the environment variables for a specified redshift function.

    getCatalog(self, schema_name=None, table_name=None):
        Get Glue Catalog metadata of a specific Database table

    get_team_clusters(self, cluster_id=None):
        Retrieves Redshift Cluster information for the Team Cluster.

    """

    def get_connection_to_redshift(
        self,
        clusterIdentifier: str,
        DbName: str,
        DbUser: str,
        lambdaName: Optional[str] = None,
    ) -> Dict[str, Union[str, sa.engine.Engine]]:
        """
        Connect to an existing cluster or create a new cluster if it does not exists.

        Note
        ----
        To connect to existing cluster:
            **Cluster networking is configured correctly (has access to the Orbit Workbench VPC).
            **Cluster ESG was created, assigned to the cluster.
            **The ESG should have an ingress rule to allow inbound tcp on the redshift port from the Orbit Workbench
                instance SG.
            **A new teamspace should be launched from the Service Catalog and the ESG should be passed as a parameter
                to allow external traffic.

        Parameters
        ----------
        clusterIdentifier : str
            A unique name of the Redshift cluster, can be a new/existing cluster as well. If used with existing cluster,
            lambdaName should be given as well.
        DbName : str
            The Redshift DB name to connect to.
        DbUser : str
            The Redshift User name to connect with.
        lambdaName : str, optional
            For new cluster/mandatory for existing cluster connection, the lambda name which is responsible to get the
            cluster credentials.


        Returns
        -------
        db_url : str
            A sql alchemy connection string
        engine : sqlalchemy.engine.Engine
            A sql alchemy engine
        redshift_role : str
            The redshift role ARN that can be used to connect to Glue catalog

        (e.g. {'db_url': 'redshift+psycopg2://..', 'engine': engine,
        'redshift_role': 'arn:aws:iam::{accountid}:role/...'})

        Example
        --------
        >>> from aws.utils.notebooks.database import get_redshift
        >>> import json, urllib.parse
        >>> from sqlalchemy.engine import create_engine
        >>> response = get_redshift().get_connection_to_redshift(
        ...     clusterIdentifier = "my_cluster",
        ...     DbName = "my_database",
        ...     DBUser = "my_user",
        ...     lambdaName = None
        ...     )

        """

        redshift = boto3.client("redshift")

        if lambdaName:
            # Trying to get user and temp password from cluster
            try:
                lambda_client = boto3.client("lambda")
                response = lambda_client.invoke(
                    InvocationType="RequestResponse",
                    FunctionName=lambdaName,
                    Payload=json.dumps(
                        {
                            "DbUser": DbUser,
                            "DbName": DbName,
                            "clusterIdentifier": clusterIdentifier,
                        }
                    ),
                )

                # Parsing into JSON format
                data = json.loads(response["Payload"].read().decode("utf-8"))
                DbPassword = data["DbPassword"]
                DbUser = data["DbUser"]
            except Exception as e:
                logger.error(f"There was an error getting the cluster details: {data}")
                raise e
        else:
            response = redshift.get_cluster_credentials(
                DbUser=DbUser,
                DbName=DbName,
                AutoCreate=True,
                ClusterIdentifier=clusterIdentifier,
            )
            DbPassword = urllib.parse.quote(response["DbPassword"])
            DbUser = urllib.parse.quote(response["DbUser"])

        # Get the rest of the cluster properties
        clusterInfo = redshift.describe_clusters(ClusterIdentifier=clusterIdentifier)

        hostName = clusterInfo["Clusters"][0]["Endpoint"]["Address"]
        port = clusterInfo["Clusters"][0]["Endpoint"]["Port"]

        self.db_url = "redshift+psycopg2://{}:{}@{}:{}/{}".format(DbUser, DbPassword, hostName, port, DbName)
        if clusterInfo["Clusters"][0]["IamRoles"]:
            self.redshift_role = clusterInfo["Clusters"][0]["IamRoles"][0]["IamRoleArn"]
        else:
            self.redshift_role = None
        self.current_engine = create_engine(self.db_url)
        self.db_class = "redshift"
        return {
            "db_url": self.db_url,
            "engine": self.current_engine,
            "redshift_role": self.redshift_role,
        }

    def create_external_schema(self, schema_name: str, glue_database: str) -> None:
        """
        Creates external schema if it does not already exist from a glue data catalog database.

        Parameters
        ----------
        schema_name : str
            Name of the external schema that will be created.

        glue_database : str
            Name of the source database for creating the schema.

        Returns
        -------
        None
            None.

        Example
        -------
        >>> from aws.utils.notebooks.database import RedshiftUtils
        >>> RedshiftUtils.create_external_schema(schema_name="my_schema", glue_database="my_database")
        """

        createSchemaSql = f"create external schema IF NOT EXISTS {schema_name} from data catalog database '{glue_database}'\n iam_role '{self.redshift_role}'"
        self.execute_ddl(createSchemaSql, dict())

    def create_external_table(
        self,
        select: str,
        database_name: str,
        table_name: str,
        format: Optional[str] = "Parquet",
        s3_location: Optional[str] = None,
        options: Optional[str] = "",
    ) -> IPython.core.display.JSON:
        """
        Creates a new external table in the given database and runs a glue crawler to populate glue catalog tables with
        table metadata.

        Note
        ----
        This method function uses Amazon Redshift UNLOAD which splits the results of a select statement across a set of
        files, one or more files per node slice, to simplify parallel reloading of the data.

        Parameters
        ----------
        select : str
            SQL ddl statement for data to select (e.g. 'select * from table').
        database_name : str
            Name of database with existing data and schema.
        table_name : str
            The name of the table to be created.
        format : str, optional
            The file format for data files (default Parquet format).
        s3_location : str, optional
            The path to the Amazon S3 bucket or folder that contains the data files or a manifest file that contains a
            list of Amazon S3 object paths (used only if no database has no location).
        options : str, optional
            Specify additional table properties for when creating new table.

        Returns
        -------
        s : IPython.core.display.JSON
            An IPython JSON display representing the schema metadata for the table(s) / database

        Example
        --------
        >>> from aws.utils.notebooks.database import RedshiftUtils
        >>> from aws.utils.notebooks.json import display_json
        >>> RedshiftUtils.create_external_table(
        ...     select = 'select * from table1',
        ...     database_name = 'my_database',
        ...     table_name = 'myQuery1',
        ...     s3_location = 's3://bucketname/folder/'
        ... )
        """
        glue = boto3.client("glue")
        target_s3 = glue.get_database(Name=database_name)["Database"]["LocationUri"]
        s3 = boto3.client("s3")

        if target_s3 == None or len(target_s3) == 0:
            if s3_location != None:
                target_s3 = s3_location
            else:
                raise Exception("Database does not have a location , and location was not provided")
        bucket_name = target_s3[5:].split("/")[0]
        db_path = "/".join(target_s3[5:].split("/")[1:])
        s3_path = f"{target_s3}/{table_name}/"
        prefix = f"{db_path}/{table_name}/"
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if "Contents" in response:
            for object in response["Contents"]:
                logger.info("Deleting {object['Key']}")
                s3.delete_object(Bucket=bucket_name, Key=object["Key"])

        ddl = f"""
            UNLOAD ('{select}')
                    TO '{s3_path}' iam_role '{self.redshift_role}'
                    FORMAT AS {format}
                    {options}
        """

        self.execute_ddl(ddl)

        logger.info("Query result s3 write complete.")

        run_crawler(f"crawler_for_{database_name}_{table_name}", database_name, s3_path)

        response = glue.get_table(DatabaseName=database_name, Name=table_name)

        recordCount = response["Table"]["Parameters"]["recordCount"]
        schema = response["Table"]["StorageDescriptor"]["Columns"]
        location = response["Table"]["StorageDescriptor"]["Location"]
        data_format = response["Table"]["Parameters"]["classification"]
        logger.info(f"Table {table_name} created: records: {recordCount}, format: {data_format}, location: {location}")
        s = {}
        for c in schema:
            s[c["Name"]] = c["Type"]
        return display_json(s, root="cols")

    def connect_to_redshift(
        self,
        cluster_name: str,
        reuseCluster: Optional[str] = True,
        startCluster: Optional[str] = False,
        clusterArgs: Optional[Dict[str, str]] = dict(),
    ) -> Dict[str, Union[str, sa.engine.Engine, bool]]:
        """
        Connects to a Redshift Cluster and returns connection information once redshift cluster is available for use.

        Parameters
        ----------
        cluster_name : str
            Name of the redshift cluster
        reuseCluster : bool, optional
            Boolean determining if you wish to reuse an existing cluster name (default True).
        startCluster : bool, optional
            Boolean determining if you wish to start a new cluster (default False)
        clusterArgs : dict(), optional
            Other redshift parameters you can optionally specify (e.g. auto_analyze, max_concurrency_scaling_clusters,
            statement_timeout, etc.)

        Returns
        -------
        db_url : str
            A sqlalchemy connection string.
        engine: sqlalchemy.engine.Engine
            A sql alchemy engine.
        cluster_identifier: str
            The unique identifier of the cluster.
        started: bool
            Boolean representing if cluster has started or not.
        redshift_role: str
            The redshift role ARN that can be used to access other AWS services when you execute the Amazon Redshift
            command.


        Examples
        --------
        >>> from aws.utils.notebooks.database import RedshiftUtils
        >>> from aws.utils.notebooks.common import get_properties
        >>> RedshiftUtils.connect_to_redshift(cluster_name= 'cluster-test')

        """

        props = get_properties()
        redshift = boto3.client("redshift")
        env = props["AWS_ORBIT_ENV"]
        team_space = props["AWS_ORBIT_TEAM_SPACE"]
        cluster_identifier = f"orbit-{env}-{team_space}-{cluster_name}".lower()
        try:
            clusters = redshift.describe_clusters(ClusterIdentifier=cluster_identifier)["Clusters"]
        except:
            clusters = []

        started = False
        if reuseCluster:
            if not clusters:
                if not startCluster:
                    raise Exception("cannot find running Redshift cluster: " + cluster_identifier)
                else:
                    (cluster_identifier, user) = self._start_and_wait_for_redshift(
                        redshift, cluster_identifier, props, clusterArgs
                    )
                    started = True
            else:
                logger.info("Using internal cluster")
                user = "master"
        else:
            if not startCluster:
                raise Exception("If reuseCluster is False , then startCluster must be True")
            else:
                (cluster_identifier, user) = self._start_and_wait_for_redshift(
                    redshift, cluster_identifier, props, clusterArgs
                )
                started = True

        conn = self.get_connection_to_redshift(cluster_identifier, "defaultdb", user)

        return {
            "db_url": conn["db_url"],
            "engine": conn["engine"],
            "cluster_identifier": cluster_identifier,
            "started": started,
            # 'user': user,
            # 'password': password,
            "redshift_role": conn["redshift_role"],
        }

    def _get_cred_to_redshift_cluster(self, cluster_name: str) -> Dict[str, str]:

        """
        Invokes Lambda Function to Connect to a Redshift Cluster and returns user credentials (username and password)
        upon successful connection.

        """
        props = get_properties()
        funcName = "ConnectToRedshiftFunction"

        orbit = props["AWS_ORBIT_ENV"]
        team_space = props["AWS_ORBIT_TEAM_SPACE"]
        functionName = "{}-{}-{}".format(orbit, team_space, funcName)
        lambda_client = boto3.client("lambda")

        invoke_response = lambda_client.invoke(
            FunctionName=functionName,
            Payload=bytes(json.dumps({"cluster_name": cluster_name}), "utf-8"),
            InvocationType="RequestResponse",
            LogType="Tail",
        )
        response_payload = json.loads(invoke_response["Payload"].read().decode("utf-8"))
        if "200" != response_payload["statusCode"]:
            logger.error(response_payload)
            raise Exception("could not connect to cluster")

        return {
            "user": response_payload["user"],
            "password": response_payload["password"],
        }

    def delete_redshift_cluster(self, cluster_name: str) -> None:

        """
        Deletes a redshift cluster.

        Parameters
        ----------
        cluster_name : str
            The Redshift cluster name given when creating the cluster

        Returns
        -------
        None
            None.

        Example
        --------
        >>> from aws.utils.notebooks.database import RedshiftUtils
        >>> from aws.utils.notebooks.common import get_properties
        >>> RedshiftUtils.delete_redshift_cluster(cluster_name = "my_cluster")

        """

        props = get_properties()
        env = props["AWS_ORBIT_ENV"]
        team_space = props["AWS_ORBIT_TEAM_SPACE"]
        redshift = boto3.client("redshift")
        namespace = f"orbit-{env}-{team_space}-"
        cluster_name_value = cluster_name.lower()
        cluster_identifier = cluster_name if namespace in cluster_name_value else namespace + cluster_name_value
        res = redshift.delete_cluster(ClusterIdentifier=cluster_identifier, SkipFinalClusterSnapshot=True)

        if "errorMessage" in res:
            logger.error(res["errorMessage"])
        else:
            logger.info("Cluster termination started")

        return

    def get_redshift_functions(self) -> List[str]:
        """
        Provides a list of Redshift Functions that can be used.

        Parameters
        ----------
        None
            None.

        Returns
        -------
        functions: list
            List of Redshift Functions

        Examples
        --------
        >>> from aws.utils.notebooks.database import get_redshift
        >>> get_redshift().get_redshift_functions()
        """

        return list(self._get_redshift_functions().keys())

    def describe_redshift_function(self, funcName: str) -> Dict[str, str]:
        """
        Returns the environment variables for a specified redshift function.

        Parameters
        ----------
        funcName : str
            Name of a redshift function

        Returns
        -------
        description : Dict[str, str]
            Key-Value pairs of names and descriptions of the given redshift function environment variables.

        Examples
        --------
        >>> from aws.utils.notebooks.database import get_redshift
        >>> get_redshift().describe_redshift_function(funcName = 'get_connection_to_redshift')
        """

        return self._get_redshift_functions()[funcName]

    def _get_redshift_functions(self) -> Dict[str, Dict[str, str]]:
        """
        Returns a dictionary of all redshift function names  with their parameters/configuration
        using Lambda.list_functions().
        """

        lambda_client = boto3.client("lambda")
        props = get_properties()
        env_name = props["AWS_ORBIT_ENV"]
        team_space = props["AWS_ORBIT_TEAM_SPACE"]
        namespace = f"{env_name}-{team_space}"
        funcs = []
        while True:
            response = lambda_client.list_functions()
            token = response["NextMarker"] if "NextMarker" in response else None
            for func in response["Functions"]:
                if (
                    namespace in func["FunctionName"]
                    and "Environment" in func
                    and "Variables" in func["Environment"]
                    and "RedshiftClusterParameterGroup" in func["Environment"]["Variables"]
                    and "StartRedshift" in func["FunctionName"]
                ):
                    funcs.append(func)
            if token == None:
                break

        func_descs = {}

        for f in funcs:
            user_name = f["FunctionName"][f["FunctionName"].index("StartRedshift") + len("StartRedshift-") :]
            func_desc = f["Environment"]["Variables"]
            del func_desc["RedshiftClusterParameterGroup"]
            del func_desc["RedshiftClusterSubnetGroup"]
            del func_desc["RedshiftClusterSecurityGroup"]
            del func_desc[ORBIT_ENV]
            del func_desc[AWS_ORBIT_TEAM_SPACE]
            del func_desc["SecretId"]
            del func_desc["PortNumber"]
            del func_desc["Role"]
            func_descs[user_name] = func_desc

        return func_descs

    def _start_and_wait_for_redshift(
        self,
        redshift: boto3.client("redshift"),
        cluster_name: str,
        props: Dict[str, str],
        clusterArgs: Dict[str, str],
    ) -> Tuple[str, str]:
        """
        Starts the Redshift Cluster and waits until cluster is available for use.

        """
        env = props["AWS_ORBIT_ENV"]
        team_space = props["AWS_ORBIT_TEAM_SPACE"]
        funcName = f"Standard"
        if "redshift_start_function" in clusterArgs.keys():
            funcName = clusterArgs["redshift_start_function"]

        cluster_def_func = f"orbit-{env}-{team_space}-StartRedshift-{funcName}"

        lambda_client = boto3.client("lambda")
        clusterArgs["cluster_name"] = cluster_name
        invoke_response = lambda_client.invoke(
            FunctionName=cluster_def_func,
            Payload=bytes(json.dumps(clusterArgs), "utf-8"),
            InvocationType="RequestResponse",
            LogType="Tail",
        )

        response_payload = json.loads(invoke_response["Payload"].read().decode("utf-8"))
        if "statusCode" not in response_payload or "200" != response_payload["statusCode"]:
            logger.error(response_payload)
            raise Exception("could not start cluster")

        cluster_id = response_payload["cluster_id"]
        user = response_payload["username"]
        logger.info("cluster created: %s", cluster_id)
        logger.info("waiting for created cluster: %s", cluster_id)
        waiter = redshift.get_waiter("cluster_available")
        waiter.wait(ClusterIdentifier=cluster_id, WaiterConfig={"Delay": 60, "MaxAttempts": 15})
        time.sleep(60)  # allow DB to for another min
        return (cluster_id, user)

    def create_cluster(self, cluster_name: str, number_of_nodes: str, node_type: str) -> Dict[str, str]:
        """
        Creates a Redshift Cluster.

        """
        props = get_properties()
        env = props["AWS_ORBIT_ENV"]
        team_space = props["AWS_ORBIT_TEAM_SPACE"]
        cluster_def_func = f"orbit-{env}-{team_space}-StartRedshift-Standard"
        cluster_identifier = f"orbit-{env}-{team_space}-{cluster_name}".lower()

        cluster_args = {"cluster_name": cluster_identifier, "Nodes": number_of_nodes, "NodeType": node_type}

        lambda_client = boto3.client("lambda")
        invoke_response = lambda_client.invoke(
            FunctionName=cluster_def_func,
            Payload=bytes(json.dumps(cluster_args), "utf-8"),
            InvocationType="RequestResponse",
            LogType="Tail",
        )

        response_payload = json.loads(invoke_response["Payload"].read().decode("utf-8"))
        if "statusCode" not in response_payload or "200" != response_payload["statusCode"]:
            logger.error(response_payload)
            error_message = response_payload["errorMessage"]
            response = {"status": "400", "message": f"Error creating Redshift cluster - {error_message}"}
        else:
            cluster_id = response_payload["cluster_id"]
            logger.info("cluster created: %s", cluster_id)
            response = {
                "status": str(response_payload["statusCode"]),
                "message": f"Successfully created Redshift cluster {cluster_id}",
            }

        return response

    def _add_json_schema(
        self,
        s3: boto3.client("s3"),
        glue: boto3.client("glue"),
        table: str,
        database_name: str,
        table_name: str,
    ) -> None:
        """
        Updates schema of specified table based on Glue Catalog metadata.

        """

        response = glue.get_table(DatabaseName=database_name, Name=table_name)
        # This is another way to get the properties. however, for now we will stick with the glue way that can also work in the future for Athena
        # """
        # SELECT  tablename, parameters
        #         FROM (
        #         SELECT btrim(ext_tables.tablename::text)::character varying(128) AS tablename,
        #         btrim(ext_tables.parameters::text)::character varying(500) AS parameters
        #         FROM pg_get_external_tables() ext_tables(esoid integer, schemaname character varying, tablename character varying, "location" character varying, input_format character varying,
        #         output_format character varying, serialization_lib character varying, serde_parameters character varying, compressed integer, parameters character varying)
        #         ) A
        #         LIMIT 10
        #         ;
        #
        # """

        if "Parameters" in response["Table"]:
            params = response["Table"]["Parameters"]
            if "json.schema" in params:
                schema_path = params["json.schema"]
                (bucket, key) = split_s3_path(schema_path)
                try:
                    s3_obj = s3.get_object(Bucket=bucket, Key=key)
                    content = s3_obj["Body"].read().decode("utf-8")
                    schema = json.loads(content)
                    table["jschema"] = schema
                except Exception as e:
                    logger.error(str(e))
                    raise Exception(f"Cannot access {table_name} schema file at: {schema_path}")

    def getCatalog(
        self, schema_name: Optional[str] = None, table_name: Optional[str] = None
    ) -> IPython.core.display.JSON:
        """
        Get Glue Catalog metadata of a specific Database table.

        Parameters
        ----------
        schema_name : str, optional
            Name of schema to retrieve Glue Catalog for (default looks at all schema with give tablenames in the
            current database)

        table_name : str, optional
            Name of table to retrieve Glue Catalog for (default looks at all tables with give schemanames in the
            current database)


        Returns
        -------
        schema : IPython.core.display.JSON
            An IPython JSON display representing the schema metadata for the table(s) / database

        Example
        --------
        >>> from aws.utils.notebooks.database import RedshiftUtils
        >>> from aws.utils.notebooks.json import display_json
        >>> RedshiftUtils.getCatalog(schema_name="my_schema",table_name="table1")
        """

        glue = boto3.client("glue")
        s3 = boto3.client("s3")
        sql = """
                    SELECT cols.schemaname, cols.tablename, cols.columnname, cols.external_type, cols.columnnum, tables.location, schemas.databasename, tables.parameters
                     FROM SVV_EXTERNAL_COLUMNS cols natural join SVV_EXTERNAL_TABLES tables natural join SVV_EXTERNAL_SCHEMAS schemas
                """

        if schema_name or table_name:
            sql += "WHERE "
            if schema_name and table_name:
                sql += f"schemaname = '{schema_name}' AND tablename = '{table_name}'"
            elif schema_name:
                sql += f"schemaname = '{schema_name}'"
            elif table_name:
                sql += f"tablename = '{table_name}'"

        sql += "\n order by schemas.schemaname, tables.tablename, columnnum\n"

        rs = self.current_engine.execute(sql)
        res = rs.fetchall()
        if len(res) == 0:
            print("no external schema or tables found")
            return

        df = DataFrame(res)
        df.columns = rs.keys()
        schemas = dict()
        for row in df.itertuples():
            if row[1] not in schemas:
                schemas[row[1]] = dict()
            if row[2] not in schemas[row[1]]:
                schemas[row[1]][row[2]] = dict()
                table = schemas[row[1]][row[2]]
                table["name"] = row[2]
                table["location"] = row[6]
                table["cols"] = dict()
                self._add_json_schema(s3, glue, table, row[7], row[2])
            table = schemas[row[1]][row[2]]
            colInfo = dict()
            colInfo["name"] = row[3]
            colInfo["type"] = row[4]
            colInfo["order"] = row[5]
            table["cols"][row[3]] = colInfo

        return display_json(schemas, root="glue databases")

    def get_team_clusters(
        self, cluster_id: Optional[str] = None
    ) -> Dict[str, Dict[str, Union[str, Dict[str, Union[str, int]]]]]:
        """
        Retrieves Redshift Cluster information for the Team Cluster.

        Parameters
        ----------
        cluster_id : str, optional
            Gets information for a specific cluster Id. Default looks at cluster tagged with 'AWS_ORBIT_TEAM_SPACE'

        Returns
        -------
        clusters_info : Dict[str, Dict[str, Union[str, Dict[str, Union[str, int]]]]]
            Information on the cluster(s) and their configuration.

        Example
        --------
        >>> from aws.utils.notebooks.database import RedshiftUtils
        >>> from aws.utils.notebooks.common import get_workspace
        >>> RedshiftUtils.get_team_clusters(cluster_id= "my_cluster")

        """

        redshift = boto3.client("redshift")
        props = get_properties()
        if cluster_id == None:
            redshift_cluster_search_tag = props["AWS_ORBIT_ENV"] + "-" + props["AWS_ORBIT_TEAM_SPACE"]
            clusters = redshift.describe_clusters(TagValues=[redshift_cluster_search_tag])["Clusters"]
        else:
            clusters = redshift.describe_clusters(
                ClusterIdentifier=cluster_id,
            )["Clusters"]
        clusters_info = {}
        for cluster in clusters:
            cluster_id = cluster["ClusterIdentifier"]
            cluster_model = {}
            cluster_model["cluster_id"] = cluster_id
            cluster_model["Name"] = cluster_id
            cluster_model["State"] = cluster["ClusterStatus"]
            if "Endpoint" in cluster and "Address" in cluster["Endpoint"]:
                cluster_model["ip"] = f"{cluster['Endpoint']['Address']}:{cluster['Endpoint']['Port']}"

            cluster_nodes_info = {
                "node_type": cluster["NodeType"],
                "nodes": len(cluster["ClusterNodes"]),
            }
            cluster_model["instances"] = cluster_nodes_info
            clusters_info[cluster_id] = cluster_model
            cluster_model["info"] = cluster
        return clusters_info


class AthenaUtils(DatabaseCommon):
    """Collection of Athena functions used to easily connect and work with databases.

    Methods
    -------
    get_connection_to_athena(self, DbName, region_name=None, S3QueryResultsLocation=None):
        Connect Athena to an existing database.

    getCatalog(self, database=None):
        Get Data Catalog of a specific Database


    """

    def get_connection_to_athena(
        self,
        DbName: str,
        region_name: Optional[str] = None,
        S3QueryResultsLocation: Optional[str] = None,
    ) -> Dict[str, Union[str, sa.engine.Engine]]:
        """
        Connect Athena to an existing database

        Parameters
        ----------
        DbName : str
            Name of the glue database name.

        region_name : str, optional
            The region to connect to athena. The default region will be used if receives None.

        S3QueryResultsLocation : str, optional
            The s3 bucket where to store query results. The results will not be saved if received None.


        Returns
        -------
        db_url : str
            A sql alchemy connection string.
        engine : sqlalchemy.engine.Engine
            A sql alchemy engine.

        Example
        --------
        >>> from aws.utils.notebooks.database import AthenaUtils
        >>> from sqlalchemy.engine import create_engine
        >>> from aws.utils.notebooks.common import get_workspace
        >>> (db_url,engine) = AthenaUtils.get_connection_to_athena(
        ...     DbName = glue_db,
        ...     my_region = my_region,
        ...     S3QueryResultsLocation = results_location)
        """

        workspace = get_workspace()
        if region_name == None:
            region_name = workspace["region"]

        if S3QueryResultsLocation == None:
            S3QueryResultsLocation = f"{workspace['ScratchBucket']}/athena"

        template_con_str = (
            "awsathena+rest://athena.{region_name}.amazonaws.com:443/" "{schema_name}?s3_staging_dir={s3_staging_dir}"
        )
        conn_str = template_con_str.format(
            region_name=region_name,
            schema_name=DbName,
            s3_staging_dir=quote_plus(S3QueryResultsLocation),
        )

        engine = create_engine(conn_str)
        self.db_url = conn_str
        self.current_engine = engine
        self.db_class = "athena"
        return {
            "db_url": self.db_url,
            "engine": self.current_engine,
        }

    def getCatalog(self, database: Optional[str] = None) -> IPython.core.display.JSON:
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
        schemas = dict()
        response = glue.get_tables(DatabaseName=database, MaxResults=1000)
        for t in response["TableList"]:
            table = dict()
            schemas[t["Name"]] = table
            table["name"] = t["Name"]
            table["location"] = t["StorageDescriptor"]["Location"]
            table["cols"] = dict()
            for c in t["StorageDescriptor"]["Columns"]:
                col = dict()
                table["cols"][c["Name"]] = col
                col["name"] = c["Name"]
                col["type"] = c["Type"]

        return display_json(schemas, root="glue databases")

    def get_sample_data(self, database: str, table: str, sample: int, field: str, direction: str):
        workspace = get_workspace()
        logger.info(f"query staging location: {workspace['ScratchBucket']}/athena/query/")
        conn = pyathena.connect(
            s3_staging_dir=f"{workspace['ScratchBucket']}/athena/query/",
            region_name=workspace["region"],
        )
        if field and len(field) > 0:
            query = f'SELECT * FROM "{database}"."{table}" order by {field} desc LIMIT {sample}'
        else:
            query = f'SELECT * FROM "{database}"."{table}" LIMIT {sample}'
        df = pd.read_sql(query, conn)
        result = df.to_json(orient="records")
        return result
