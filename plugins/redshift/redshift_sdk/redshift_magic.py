#  Copyright 2019 Amazon.com, Inc. and its affiliates. All Rights Reserved.
#  #
#  Licensed under the Amazon Software License (the 'License').
#  You may not use this file except in compliance with the License.
#  A copy of the License is located at
#  #
#    http://aws.amazon.com/asl/
#  #
#  or in the 'license' file accompanying this file. This file is distributed
#  on an 'AS IS' BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
#  express or implied. See the License for the specific language governing
#  permissions and limitations under the License.

from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic, needs_local_scope)
import sql.connection
import sys
import argparse

def exception_handler(exception_type, exception, traceback):
    print("%s: %s" % (exception_type.__name__, exception), file=sys.stderr)

class ArgumentParserNoSysExit(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        raise Exception(message)

@magics_class
class DatabaseMagics(Magics):
    def __init__(self, shell,  database_utils):
        super().__init__(shell)
        self.ip = get_ipython()
        self.database_utils = database_utils

@magics_class
class RedshiftMagics(DatabaseMagics):
    def __init__(self, shell,  database_utils):
        super().__init__(shell, database_utils)

    @line_magic
    def connect_to_redshift(self,line):
        if len(line) == 0:
            print("must provide redshift cluster name")
            return

        parser = ArgumentParserNoSysExit(description='start Redshift connection')
        parser.add_argument('-cluster', required=True,
                            help='specify cluster name')
        parser.add_argument('-start',  action='store_true',
                            help='start cluster if not exists')
        parser.add_argument('-reuse', action='store_true',
                            help='reuse cluster if exists')
        parser.add_argument('-func', nargs='*', default=None,
                            help='specify cluster function name')
        try:
            args = parser.parse_args(line.strip().split(' '))
            clusterArgs = dict()
            if args.func != None:
                clusterArgs['redshift_start_function'] = args.func[0]
                for arg in args.func[1:]:
                    keypair = arg.split('=')
                    clusterArgs[keypair[0]] = keypair[1]

            connProp = self.database_utils.connect_to_redshift(cluster_name = args.cluster, reuseCluster=args.reuse, startCluster=args.start, clusterArgs=clusterArgs)
            dbUrl = connProp['db_url']
            self.ip.run_line_magic('sql', dbUrl)
            print("connected!")
        except Exception as e:
            print("Error!")
            print(str(e))

    @line_magic
    def connect_to_external_redshift(self,line):
        if len(line) == 0:
            print("must provide redshift cluster name")
            return

        parser = ArgumentParserNoSysExit(description='start Redshift connection')
        parser.add_argument('-cluster', required=True,
                            help='specify cluster name')
        parser.add_argument('-DbName', required=True,
                            help='specify DB name')
        parser.add_argument('-DbUser', required=True,
                            help='specify DB user')
        parser.add_argument('-lambdaName', default=None,
                            help='specify credentials lambda name')
        #TODO - Add DB Goup parameter to this magic and use for external redshift cluster.
        # Bring back all the work we pushed to Redshift Lambdas behind the API Gateway

        try:
            args = parser.parse_args(line.strip().split(' '))
            connProp = self.database_utils.get_connection_to_redshift(clusterIdentifier = args.cluster, DbName=args.DbName, DbUser=args.DbUser, lambdaName=args.lambdaName)
            dbUrl = connProp['db_url']
            self.ip.run_line_magic('sql', dbUrl)
            print("connected!")
        except Exception as e:
            print("Error!")
            print(str(e))

    @line_magic
    def delete_redshift_cluster(self,line):
        if len(line) == 0:
            print("must provide redshift cluster name")
            return

        parser = ArgumentParserNoSysExit(description='start Redshift connection')
        parser.add_argument('-cluster', required=True,
                            help='specify cluster name')
        try:
            args = parser.parse_args(line.strip().split(' '))
            self.database_utils.delete_redshift_cluster(args.cluster)
        except Exception as e:
            print("Error!")
            print(str(e))


    @needs_local_scope
    @cell_magic
    def ddl(self, line, cell, local_ns=None):
        self.database_utils.execute_ddl(cell,local_ns)

    @line_magic
    def catalog(self, line):
        if len(line) == 0:
            return self.database_utils.getCatalog()
        parser = ArgumentParserNoSysExit(description='display all databases, tables and columns')
        parser.add_argument('-s', nargs='?', default=None,
                            help='specify external schema name')
        parser.add_argument('-t', nargs='?', default=None,
                            help='specify external table name')

        try:
            args = parser.parse_args(line.strip().split(' '))
            return self.database_utils.getCatalog(schema_name=args.s, table_name=args.t)
        except Exception as e:
            print("Error!")
            print(str(e))

    @line_magic
    def create_external_schema(self,line):
        if len(line) == 0:
            return self.database_utils.getCatalog()
        parser = ArgumentParserNoSysExit(description='create external schema in Redshift to point to Glue Catalog')
        parser.add_argument('-s', nargs='?', default=None,
                            help='specify external schema name')
        parser.add_argument('-g', nargs='?', default=None,
                            help='specify glue database')

        try:
            args = parser.parse_args(line.strip().split(' '))

            self.database_utils.create_external_schema(schema_name = args.s, glue_database =args.g)
        except Exception as e:
            print("Error!")
            print(str(e))

    @cell_magic
    def create_external_table(self, line, cell, local_ns=None):
        if len(line) == 0:
            return self.database_utils.getCatalog()
        parser = ArgumentParserNoSysExit(description='create external table in S3 and Glue Catalog')
        parser.add_argument('-g',
                            help='specify glue database name')
        parser.add_argument('-t',
                            help='specify table name')
        parser.add_argument('-f', nargs='?', default='parquet', choices=['parquet', 'csv'],
                            help='specify file format')
        parser.add_argument('-l', nargs='?', default=None,
                            help='specify s3 location or leave out to use Glue DB location')
        parser.add_argument('-u', nargs='?', default='',
                            help='other unload properties')

        try:
            args = parser.parse_args(line.strip().split(' '))

            return self.database_utils.create_external_table(select=cell,database_name=args.g, table_name=args.t, format=args.f, s3_location=args.l, options=args.u)
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

