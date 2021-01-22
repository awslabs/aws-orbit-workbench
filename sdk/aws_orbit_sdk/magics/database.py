import argparse
import sys
from typing import Any, Dict, Optional

import IPython.display
import sql.connection
from IPython import get_ipython
from IPython.core.magic import Magics, cell_magic, line_magic, magics_class, needs_local_scope
from IPython.display import JSON


def exception_handler(exception_type, exception, traceback):
    print("%s: %s" % (exception_type.__name__, exception), file=sys.stderr)


class ArgumentParserNoSysExit(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        raise Exception(message)


@magics_class
class DatabaseMagics(Magics):
    """
    Database functions, inherited by both Redshift and Athena classes.
    """

    def __init__(self, shell, database_utils):
        super().__init__(shell)
        self.ip = get_ipython()
        self.database_utils = database_utils


@magics_class
class RedshiftMagics(DatabaseMagics):
    """
    Redshift Custom Magic functions used to easily connect and work with databases.

    Methods
    -------
    %connect_to_redshift:
        Start Redshift connection
    %connect_to_external_redshift:
        Start Redshift connection
    %delete_redshift_cluster:
        Deletes a redshift cluster.
    %catalog:
        Get Glue Catalog metadata of a specific Database table.
    %create_external_schema:
        Creates external schema if it does not already exist from a glue data catalog database.
    %%ddl:
        Executes a SQL ddl statement.
    %%create_external_table:
        Create external table in S3 and Glue Catalog.
    """

    def __init__(self, shell, database_utils):
        super().__init__(shell, database_utils)

    @line_magic
    def connect_to_redshift(self, line: str) -> None:
        """
        Start Redshift connection

        Parameters
        ----------
        '-cluster' : str
            Specify cluster name
        '-start' : bool, optional
            Start cluster if it does not exists (default False)
        '-reuse' : bool, optional
            Reuse cluster if cluster name exists (default True)
        '-func' : str, optional
            Other redshift arguments(e.g. max_concurrency_scaling_clusters, etc.)(default None).


        Returns
        -------
        None
            None.

        Examples
        --------
        >>> %connect_to_redshift -cluster db-test -reuse -start -func Standard Nodes=3
        """

        if len(line) == 0:
            print("must provide redshift cluster name")
            return

        parser = ArgumentParserNoSysExit(description="start Redshift connection")
        parser.add_argument("-cluster", required=True, help="specify cluster name")
        parser.add_argument("-start", action="store_true", help="start cluster if not exists")
        parser.add_argument("-reuse", action="store_true", help="reuse cluster if exists")
        parser.add_argument("-func", nargs="*", default=None, help="specify cluster function name")
        try:
            args = parser.parse_args(line.strip().split(" "))
            clusterArgs = dict()
            if args.func != None:
                clusterArgs["redshift_start_function"] = args.func[0]
                for arg in args.func[1:]:
                    keypair = arg.split("=")
                    clusterArgs[keypair[0]] = keypair[1]

            connProp = self.database_utils.connect_to_redshift(
                cluster_name=args.cluster,
                reuseCluster=args.reuse,
                startCluster=args.start,
                clusterArgs=clusterArgs,
            )
            dbUrl = connProp["db_url"]
            self.ip.run_line_magic("sql", dbUrl)
            print("connected!")
        except Exception as e:
            print("Error!")
            print(str(e))

    @line_magic
    def connect_to_external_redshift(self, line: str) -> None:
        """
        Start Redshift connection

        Parameters
        ----------
        '-cluster' : str
            specify cluster name
        '-DbName' : str
            specify the Redshift DB name to connect to.
        '-DbUser' : str
            specify DB the Redshift User name to connect with.
        '-lambdaName' : str, optional
            For new cluster/mandatory for existing cluster connection, the lambda name which is responsible to get the
                cluster credentials.

        Returns
        -------
        None
            None.

        Example
        -------
        >>> %connect_to_external_redshift -cluster db-test -DbName mydatabase -DbUser my_user
        """

        if len(line) == 0:
            print("must provide redshift cluster name")
            return

        parser = ArgumentParserNoSysExit(description="start Redshift connection")
        parser.add_argument("-cluster", required=True, help="specify cluster name")
        parser.add_argument("-DbName", required=True, help="specify DB name")
        parser.add_argument("-DbUser", required=True, help="specify DB user")
        parser.add_argument("-lambdaName", default=None, help="specify credentials lambda name")
        try:
            args = parser.parse_args(line.strip().split(" "))
            connProp = self.database_utils.get_connection_to_redshift(
                clusterIdentifier=args.cluster,
                DbName=args.DbName,
                DbUser=args.DbUser,
                lambdaName=args.lambdaName,
            )
            dbUrl = connProp["db_url"]
            self.ip.run_line_magic("sql", dbUrl)
            print("connected!")
        except Exception as e:
            print("Error!")
            print(str(e))

    @line_magic
    def delete_redshift_cluster(self, line: str) -> None:
        """
        Deletes a redshift cluster.

        Parameters
        ----------
        '-cluster' : str
            The Redshift cluster name

        Returns
        -------
        None
            None.

        Example
        --------
        >>> %delete_redshift_cluster -cluster db-test
        """

        if len(line) == 0:
            print("must provide redshift cluster name")
            return

        parser = ArgumentParserNoSysExit(description="start Redshift connection")
        parser.add_argument("-cluster", required=True, help="specify cluster name")
        try:
            args = parser.parse_args(line.strip().split(" "))
            self.database_utils.delete_redshift_cluster(args.cluster)
        except Exception as e:
            print("Error!")
            print(str(e))

    @needs_local_scope
    @cell_magic
    def ddl(self, line: str, cell: str, local_ns: Optional[Dict[str, str]] = None) -> None:
        """
        Executes a SQL ddl statement.

        Parameters
        ----------
        cell : str
            The data descrption language statement to execute in SQL.
        local_ns : str
            The namespace to load into IPython user namespace

        Returns
        -------
        None
            None.

        Examples
        --------
        >>>%%ddl
        >>>drop table if exists mydatabase.Table3
        """

        self.database_utils.execute_ddl(cell, local_ns)

    @line_magic
    def catalog(self, line: str) -> IPython.core.display.JSON:
        """
        Get Glue Catalog metadata of a specific Database table.

        Parameters
        ----------
        -s : str, optional
            Name of schema to retrieve Glue Catalog for (default looks at all schema with given table names in the
            current database)

        -t : str, optional
            Name of table to retrieve Glue Catalog for (default looks at all tables with given schema names in the
            current database)

        Returns
        -------
        schema : IPython.core.display.JSON
            An IPython JSON display representing the schema metadata for the table(s) / database

        Example
        --------
        >>> %catalog -s database_ext_schema
        """

        if len(line) == 0:
            return self.database_utils.getCatalog()
        parser = ArgumentParserNoSysExit(description="display all databases, tables and columns")
        parser.add_argument("-s", nargs="?", default=None, help="specify external schema name")
        parser.add_argument("-t", nargs="?", default=None, help="specify external table name")

        try:
            args = parser.parse_args(line.strip().split(" "))
            return self.database_utils.getCatalog(schema_name=args.s, table_name=args.t)
        except Exception as e:
            print("Error!")
            print(str(e))

    @line_magic
    def create_external_schema(self, line: str) -> None:
        """
        Creates external schema if it does not already exist from a glue data catalog database.

        Parameters
        ----------
        -s : str
            Name of the external schema that will be created.

        -g : str
            Name of the glue database for creating the schema.

        Returns
        -------
        None
            None.

        Example
        --------
        >>> %create_external_schema -s users -g users
        """
        if len(line) == 0:
            return self.database_utils.getCatalog()
        parser = ArgumentParserNoSysExit(description="create external schema in Redshift to point to Glue Catalog")
        parser.add_argument("-s", nargs="?", default=None, help="specify external schema name")
        parser.add_argument("-g", nargs="?", default=None, help="specify glue database")

        try:
            args = parser.parse_args(line.strip().split(" "))

            self.database_utils.create_external_schema(schema_name=args.s, glue_database=args.g)
        except Exception as e:
            print("Error!")
            print(str(e))

    @cell_magic
    def create_external_table(
        self, line: str, cell: str, local_ns: Optional[Dict[str, str]] = None
    ) -> IPython.core.display.JSON:
        """
        Create external table in S3 and Glue Catalog

        Parameters
        ----------
        -g : str
            Name of database with existing data and schema.
        -t :
            The name of the table to be created.
        -f : str, optional
            The file format for data files (default Parquet format).
        -l : str, optional
            The path to the Amazon S3 bucket or folder that contains the data files or a manifest file that contains a
            list of Amazon S3 object paths (used only if no database has no location).
        -u : str, optional
            Specify additional unload properties for when creating new table.

        Returns
        -------
        s : IPython.core.display.JSON
            An IPython JSON display representing the schema metadata for the table(s) / database

        Example
        --------
        >>> %%create_external_table -g users -t myQuery1
        >>> select c.id as id1,c.status from users.Table1 as c
        """
        if len(line) == 0:
            return self.database_utils.getCatalog()
        parser = ArgumentParserNoSysExit(description="create external table in S3 and Glue Catalog")
        parser.add_argument("-g", help="specify glue database name")
        parser.add_argument("-t", help="specify table name")
        parser.add_argument(
            "-f",
            nargs="?",
            default="parquet",
            choices=["parquet", "csv"],
            help="specify file format",
        )
        parser.add_argument(
            "-l",
            nargs="?",
            default=None,
            help="specify s3 location or leave out to use Glue DB location",
        )
        parser.add_argument("-u", nargs="?", default="", help="other unload properties")

        try:
            args = parser.parse_args(line.strip().split(" "))

            return self.database_utils.create_external_table(
                select=cell,
                database_name=args.g,
                table_name=args.t,
                format=args.f,
                s3_location=args.l,
                options=args.u,
            )
        except Exception as e:
            print("Error!")
            print(str(e))

    #
    # def apt_completers(self, event):
    #     """ This should return a list of strings with possible completions.
    #
    #     Note that all the included strings that don't start with event.symbol
    #     are removed, in order to not confuse readline.
    #     """
    #     return ['update', 'upgrade', 'install', 'remove']
    #
    #     completerlib.quick_completer('SELECT', ['FROM','WHERE', 'GROUPBY'])
    #
    # magics_class


@magics_class
class AthenaMagics(DatabaseMagics):
    """
    Collection of Athena Magics functions used to easily connect and work with databases.

    Methods
    -------
    %connect_to_athena:
        Connect Athena to an existing database
    %catalog:
        Get Data Catalog and display all databases, tables and columns

    """

    def __init__(self, shell, database_utils):
        super().__init__(shell, database_utils)

    @line_magic
    def connect_to_athena(self, line: str) -> None:
        """
        Connect Athena to an existing database

        Parameters
        ----------
        -database : str
            Name of the glue database name.

        Returns
        -------
        None
            None.

        Example
        --------
        >>> %connect_to_athena -database users_data
        """

        if len(line) == 0:
            print("must provide an athena database name")
            return

        parser = ArgumentParserNoSysExit(description="start Redshift connection")
        parser.add_argument("-database", required=True, help="specify database name")
        try:
            args = parser.parse_args(line.strip().split(" "))
            connProp = self.database_utils.get_connection_to_athena(args.database)
            dbUrl = connProp["db_url"]
            self.ip.run_line_magic("sql", dbUrl)
            print("connected!")
        except Exception as e:
            print("Error!")
            print(str(e))

    @line_magic
    def close_athena(self, line: str) -> None:
        """
        Close all Athena connections opened in the notebook

        Returns
        -------
        None
            None.

        Example
        --------
        >>> %close_athena
        """
        sqlmagic_connections = sql.connection.Connection.connection
        for conn_key in list(sqlmagic_connections.keys()):
            conn = sqlmagic_connections[conn_key]
            conn.session.close()
        print("Connections closed")

    @line_magic
    def catalog(self, line: str) -> IPython.core.display.JSON:
        """
        Get Data Catalog and display all databases, tables and columns

        Parameters
        ----------
        -database : str, optional
            Name of database to catalog (default looks at all databases).

        Returns
        -------
        schema : IPython.core.display.JSON
            An IPython JSON display representing the schema metadata for a database

        Example
        --------
        >>> %catalog -database users_data
        """
        if len(line) == 0:
            return self.database_utils.getCatalog()
        parser = ArgumentParserNoSysExit(description="display all databases, tables and columns")
        parser.add_argument(
            "-database",
            nargs="?",
            default=None,
            required=True,
            help="specify database name ",
        )

        try:
            args = parser.parse_args(line.strip().split(" "))
            return self.database_utils.getCatalog(database=args.database)
        except Exception as e:
            print("Error!")
            print(str(e))
