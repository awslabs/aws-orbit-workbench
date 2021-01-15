import urllib.parse
import psycopg2
import sqlalchemy as sa
import boto3
from urllib.parse import quote_plus
from sqlalchemy.engine import create_engine
import json
import logging
from ..common import *
from ..common import AWSRequestsAuth
import time
from sqlalchemy.orm import sessionmaker
from pandas import DataFrame
from ..json import display_json
from ..glue.catalog import run_crawler
import sqlparse
import requests


logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()

class DatabaseCommon:
    current_engine = None
    db_url = None
    redshift_role = None
    db_class = None

    def execute_ddl(self,ddl,namespace=dict()):
        with self.current_engine.connect() as conn:
            session = sessionmaker(bind=self.current_engine)()
            session.connection().connection.set_isolation_level(0)
            session.execute(ddl, namespace)
            conn.close()

    def execute_query(self, sql,namespace=dict()):
        with self.current_engine.connect() as conn:
            rs = self.current_engine.execute(sql,namespace)
            conn.close()
        return rs


#To abstract Redshift and Lambda boto3 calls via VPC endpoint.
class RedshiftCommunicationViaApiHelper():
    '''
    Helper class to interact with Lambdas outside of VPC via API Gateway
    '''
    def __init__(self):
        super().__init__()
        self.props = get_properties()
        self.env = self.props['AWS_DATAMAKER_ENV']
        self.team_space = self.props['DATAMAKER_TEAM_SPACE']

    def cluster_credentials(self, request_payload):
        return self.call_api(request_payload, 'cluster_credentials')

    def create_cluster(self, request_payload):
        return self.call_api(request_payload,'create_cluster')

    def describe_cluster(self, request_payload):
        return self.call_api(request_payload,'describe_cluster')
    def delete_cluster(self, request_payload):
        return self.call_api(request_payload,'delete_cluster')

    def get_api_config(self):
        apigateway_key = f"/datamaker/env/{self.env}/{self.team_space}/apigateway/config"
        ssm_client = boto3.client("ssm")
        apigateway_config_str = ssm_client.get_parameter(
            Name=apigateway_key
        )['Parameter']['Value']

        apigateway_config = json.loads(apigateway_config_str)
        return apigateway_config

    def get_session_auth(self,api_host, env_region):
        session = boto3.Session()
        credentials = session.get_credentials()
        # Credentials are refreshable, so accessing your access key / secret key
        # separately can lead to a race condition. Use this to get an actual matched set.
        #logger.info(session.profile_name)
        credentials = credentials.get_frozen_credentials()
        access_key = credentials.access_key
        secret_key = credentials.secret_key
        secret_token = credentials.token
        auth = AWSRequestsAuth(aws_access_key=access_key,
                               aws_secret_access_key=secret_key,
                               aws_host=f'{api_host}.execute-api.{env_region}.amazonaws.com',
                               aws_region=env_region,
                               aws_service='execute-api',
                               aws_token=secret_token)
        return auth

    def call_api(self, request_payload,activity):
        # Get api and env details from ssm
        apigateway_config = self.get_api_config()
        api_host = apigateway_config['api_id']
        env_region = apigateway_config['env_region']
        deploy_stage = apigateway_config['deploy_stage']
        # Get session credentials
        auth = self.get_session_auth(api_host, env_region)
        redshift_api_url = f'https://{api_host}.execute-api.{env_region}.amazonaws.com/{deploy_stage}/{self.env}/{self.team_space}/v1/redshift/{activity}'
        #logger.info(f'redshift_api_url={redshift_api_url}')
        api_response = requests.post(redshift_api_url, auth=auth, data= json.dumps(request_payload))
        #logger.info(api_response.text)
        return json.loads(api_response.text)



class RedshiftUtils(DatabaseCommon):

    def __init__(self):
        super().__init__()
        self.apihelper = RedshiftCommunicationViaApiHelper()

    def get_connection_to_redshift(self, cluster_identifier, db_name, db_user, props):
        #logger.info(f"*Starting get_connection_to_redshift")
        payload = {
            "db_user": db_user,
            "db_name": db_name,
            'cluster_identifier': cluster_identifier,
            'activity': 'cluster_credentials'
        }
        redshift_connection_dict = self.apihelper.cluster_credentials(payload)
        #logger.info(f'redshift_connection_dict={redshift_connection_dict}')
        self.db_url = redshift_connection_dict['db_url']
        #logger.info(f'self.db_url={self.db_url}')
        self.current_engine = create_engine(self.db_url)
        self.db_class = 'redshift'
        self.redshift_role=  redshift_connection_dict['redshift_role']
        #logger.info(f"*Ending get_connection_to_redshift")
        return {
            'db_url': self.db_url,
            'engine': self.current_engine,
            'redshift_role': self.redshift_role
        }
    # @Depricated - TODO - Clean
    def get_connection_to_redshift_old(self, clusterIdentifier, DbName, DbUser, lambdaName=None):
        redshift = boto3.client('redshift')

        if lambdaName:
            # Trying to get user and temp password from cluster
            try:
                lambda_client = boto3.client('lambda')
                response = lambda_client.invoke(
                    InvocationType='RequestResponse',
                    FunctionName=lambdaName,
                    Payload=json.dumps({
                        "DbUser": DbUser,
                        "DbName": DbName,
                        'clusterIdentifier': clusterIdentifier
                    })
                )

                # Parsing into JSON format
                data = json.loads(response['Payload'].read().decode('utf-8'))
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
                ClusterIdentifier=clusterIdentifier
            )
            DbPassword = urllib.parse.quote(response['DbPassword'])
            DbUser = urllib.parse.quote(response['DbUser'])

        # Get the rest of the cluster properties
        clusterInfo = redshift.describe_clusters(
            ClusterIdentifier=clusterIdentifier
        )

        hostName = clusterInfo['Clusters'][0]['Endpoint']['Address']
        port = clusterInfo['Clusters'][0]['Endpoint']['Port']

        self.db_url = 'redshift+psycopg2://{}:{}@{}:{}/{}'.format(DbUser, DbPassword, hostName, port, DbName)
        if clusterInfo['Clusters'][0]['IamRoles']:
            self.redshift_role = clusterInfo['Clusters'][0]['IamRoles'][0]['IamRoleArn']
        else:
            self.redshift_role = None
        self.current_engine = create_engine(self.db_url)
        self.db_class = 'redshift'
        return {
            'db_url': self.db_url,
            'engine': self.current_engine,
            'redshift_role': self.redshift_role
        }

    def create_external_schema(self, schema_name, glue_database):
        createSchemaSql = f"create external schema IF NOT EXISTS {schema_name} from data catalog  database '{glue_database}'\n iam_role '{self.redshift_role}'"
        self.execute_ddl(createSchemaSql, dict())

    def create_external_table(self, select, database_name, table_name, format="Parquet", s3_location=None, options=""):
        """
        :param schema_name:
        :param glue_database:
        :return:
        """
        glue = boto3.client('glue')
        target_s3 = glue.get_database(Name=database_name)['Database']['LocationUri']
        s3 = boto3.client('s3')

        if target_s3 == None or len(target_s3) == 0:
            if s3_location != None:
                target_s3 = s3_location
            else:
                raise Exception("Database does not have a location , and location was not provided")
        bucket_name = target_s3[5:].split('/')[0]
        db_path = '/'.join(target_s3[5:].split('/')[1:])
        s3_path = f'{target_s3}/{table_name}/'
        prefix = f'{db_path}/{table_name}/'
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' in response:
            for object in response['Contents']:
                logger.info("Deleting {object['Key']}")
                s3.delete_object(Bucket=bucket_name, Key=object['Key'])

        ddl = f"""
            UNLOAD ('{select}') 
                    TO '{s3_path}' iam_role '{self.redshift_role}'
                    FORMAT AS {format} 
                    {options}
        """

        self.execute_ddl(ddl)

        logger.info("Query result s3 write complete.")

        run_crawler(f'crawler_for_{database_name}_{table_name}', database_name, s3_path)

        response = glue.get_table(DatabaseName=database_name, Name=table_name)

        recordCount = response['Table']['Parameters']['recordCount']
        schema = response['Table']['StorageDescriptor']['Columns']
        location = response['Table']['StorageDescriptor']['Location']
        data_format = response['Table']['Parameters']['classification']
        logger.info(f"Table {table_name} created: records: {recordCount}, format: {data_format}, location: {location}")
        s = {}
        for c in schema:
            s[c['Name']] = c['Type']
        return display_json(s, root='cols')

    def connect_to_redshift(self, cluster_name, reuseCluster=True, startCluster=False, clusterArgs=dict()):
        #logger.info(f"*Starting connect_to_redshift")
        props = get_properties()
        env = props['AWS_DATAMAKER_ENV']
        team_space = props['DATAMAKER_TEAM_SPACE']
        funcName = f'Standard'
        redshift = boto3.client('redshift')
        cluster_identifier = (
                props['AWS_DATAMAKER_ENV'] + "-" + props['DATAMAKER_TEAM_SPACE'] + "-" + cluster_name).lower()
        #logger.info(f"cluster_identifier={cluster_identifier}")

        try:
            #Commented to use new approach
            #clusters = redshift.describe_clusters(ClusterIdentifier=cluster_identifier)["Clusters"]
            describe_cluster_payload = {
                'cluster_identifier': cluster_identifier,
                'activity': 'describe_cluster'
            }
            clusters = self.apihelper.describe_cluster(describe_cluster_payload)['Clusters']
            #logger.info(f"cluster_response={clusters}")
        except:
            clusters = []
        #logger.info(f"->clusters = {clusters}")
        started = False
        if reuseCluster:
            if not clusters:
                if not startCluster:
                    raise Exception("cannot find running Redshift cluster: " + cluster_identifier)
                else:
                    (cluster_identifier, user) = self._start_and_wait_for_redshift(redshift, cluster_identifier, props,
                                                                                   clusterArgs)
                    started = True
            else:
                logger.info("Using internal cluster")
                user = 'master'
        else:
            if not startCluster:
                raise Exception("If reuseCluster is False , then startCluster must be True")
            else:
                (cluster_identifier, user) = self._start_and_wait_for_redshift(redshift, cluster_identifier, props,
                                                                               clusterArgs)
                started = True

        # conn = self.get_connection_to_redshift(cluster_identifier, 'defaultdb', user)
        conn = self.get_connection_to_redshift(cluster_identifier, 'defaultdb', user, props)
        #logger.info(f"*Ending connect_to_redshift = {conn}")
        return {
            'db_url': conn['db_url'],
            'engine': conn['engine'],
            'cluster_identifier': cluster_identifier,
            'started': started,
            # 'user': user,
            # 'password': password,
            'redshift_role': conn['redshift_role']
        }

    def _get_cred_to_redshift_cluster(self, cluster_name):
        props = get_properties()
        funcName = 'ConnectToRedshiftFunction'

        datamaker = props['AWS_DATAMAKER_ENV']
        team_space = props['DATAMAKER_TEAM_SPACE']
        functionName = "{}-{}-{}".format(datamaker, team_space, funcName)
        lambda_client = boto3.client('lambda')

        invoke_response = lambda_client.invoke(
            FunctionName=functionName,
            Payload=bytes(json.dumps({"cluster_name": cluster_name}), "utf-8"),
            InvocationType='RequestResponse',
            LogType='Tail'
        )
        response_payload = json.loads(invoke_response['Payload'].read().decode("utf-8"))
        if ("200" != response_payload['statusCode']):
            logger.error(response_payload)
            raise Exception("could not connect to cluster")

        return {
            'user': response_payload['user'],
            'password': response_payload['password']
        }

    def delete_redshift_cluster(self, cluster_name):
        props = get_properties()
        redshift = boto3.client('redshift')
        namespace = props['AWS_DATAMAKER_ENV'] + "-" + props['DATAMAKER_TEAM_SPACE'] + "-"
        cluster_identifier = cluster_name if namespace in cluster_name else namespace + cluster_name

        # Using API gateway based approach
        # res = redshift.delete_cluster(
        #     ClusterIdentifier=cluster_identifier,
        #     SkipFinalClusterSnapshot=True
        # )

        payload = {
            'cluster_identifier': cluster_identifier,
            'activity': 'delete_cluster'
        }
        res = self.apihelper.delete_cluster(payload)

        if 'errorMessage' in res:
            logger.error(res['errorMessage'])
        else:
            logger.info("Cluster termination started")

        return

    def get_redshift_functions(self):
        return list(self._get_redshift_functions().keys())

    def describe_redshift_function(self, funcName):
        return self._get_redshift_functions()[funcName]

    def _get_redshift_functions(self):
        lambda_client = boto3.client('lambda')
        props = get_properties()
        env_name = props['AWS_DATAMAKER_ENV']
        team_space = props['DATAMAKER_TEAM_SPACE']
        namespace = f'{env_name}-{team_space}'
        funcs = []
        while True:
            response = lambda_client.list_functions()
            token = response['NextMarker'] if 'NextMarker' in response else None
            for func in response['Functions']:
                if namespace in func['FunctionName'] and 'Environment' in func and 'Variables' in func['Environment'] \
                        and 'RedshiftClusterParameterGroup' in func['Environment']['Variables'] and 'StartRedshift' in \
                        func['FunctionName']:
                    funcs.append(func)
            if token == None:
                break;

        func_descs = {}

        for f in funcs:
            user_name = f['FunctionName'][f['FunctionName'].index('StartRedshift') + len('StartRedshift-'):]
            func_desc = f['Environment']['Variables']
            del func_desc['RedshiftClusterParameterGroup']
            del func_desc['RedshiftClusterSubnetGroup']
            del func_desc['RedshiftClusterSecurityGroup']
            del func_desc[DATAMAKER_ENV]
            del func_desc[DATAMAKER_TEAM_SPACE]
            del func_desc['SecretId']
            del func_desc['PortNumber']
            del func_desc['Role']
            func_descs[user_name] = func_desc

        return func_descs

    def _start_and_wait_for_redshift(self, redshift, cluster_name, props, clusterArgs):
        env = props['AWS_DATAMAKER_ENV']
        team_space = props['DATAMAKER_TEAM_SPACE']
        funcName = f'Standard'
        if 'redshift_start_function' in clusterArgs.keys():
            funcName = clusterArgs['redshift_start_function']

        cluster_def_func = f'datamaker-{env}-{team_space}-StartRedshift-{funcName}'
        clusterArgs['cluster_name'] = cluster_name
        #Commenting below
        # lambda_client = boto3.client('lambda')
        # invoke_response = lambda_client.invoke(
        #     FunctionName=cluster_def_func,
        #     Payload=bytes(json.dumps(clusterArgs), "utf-8"),
        #     InvocationType='RequestResponse',
        #     LogType='Tail'
        # )

        clusterArgs['activity'] = 'create_cluster'
        cluster_response = self.apihelper.create_cluster(clusterArgs)
        #logger.info(f'Create RedshiftCluster Response={cluster_response}')
        #user = 'master'
        user = cluster_response['username']
        print("Creating Redshift cluster. Please hold.")
        # Poll cluster for Endpoint details before fetching the connection URL.
        describe_cluster_payload = {
            'cluster_identifier': cluster_name,
            'activity': 'describe_cluster'
        }
        time.sleep(120)
        while 'Endpoint' not in self.apihelper.describe_cluster(describe_cluster_payload)['Clusters'][0]:
            print("Creating Redshift cluster. Please hold.")
            time.sleep(60)
        #logger.info(f"*Cluster {cluster_name} created")

        #Below waiter can not work from VPC
        #waiter = redshift.get_waiter('cluster_available')
        # waiter.wait(
        #     ClusterIdentifier=cluster_name,
        #     WaiterConfig={
        #         'Delay': 60,
        #         'MaxAttempts': 15
        #     }
        # )
        # End of change

        # response_payload = json.loads(invoke_response['Payload'].read().decode("utf-8"))
        # if 'statusCode' not in response_payload or "200" != response_payload['statusCode']:
        #     logger.error(response_payload)
        #     raise Exception("could not start cluster")
        #
        # cluster_id = response_payload['cluster_id']
        # user = response_payload['username']
        # logger.info('cluster created: %s', cluster_id)
        # logger.info('waiting for created cluster: %s', cluster_id)
        # waiter = redshift.get_waiter('cluster_available')
        # waiter.wait(
        #     ClusterIdentifier=cluster_id,
        #     WaiterConfig={
        #         'Delay': 60,
        #         'MaxAttempts': 15
        #     }
        # )
        #time.sleep(60)  # allow DB to for another min

        return (cluster_name, user)

    def _add_json_schema(self, s3, glue, table, database_name, table_name):
        #logger.info(f'database_name={database_name}, table_name={table_name}')
        response = glue.get_table(
            DatabaseName=database_name,
            Name=table_name
        )
        #logger.info(f'Get_table_response={response}')
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

        if 'Parameters' in response['Table']:
            params = response['Table']['Parameters']
            if 'json.schema' in params:
                schema_path = params['json.schema']
                (bucket, key) = split_s3_path(schema_path)
                try:
                    s3_obj = s3.get_object(Bucket=bucket, Key=key)
                    content = s3_obj['Body'].read().decode('utf-8')
                    schema = json.loads(content)
                    table['jschema'] = schema
                except Exception as e:
                    logger.error(str(e))
                    raise Exception(f"Cannot access {table_name} schema file at: {schema_path}")

    def getCatalog(self, schema_name=None, table_name=None):
        #logger.info('Entered getCatalog')
        glue = boto3.client('glue')
        s3 = boto3.client('s3')
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
        #logger.info(f'Get Catalog SQL={sql}')
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
                table['name'] = row[2]
                table['location'] = row[6]
                table['cols'] = dict()
                self._add_json_schema(s3, glue, table, row[7], row[2])
            table = schemas[row[1]][row[2]]
            colInfo = dict()
            colInfo['name'] = row[3]
            colInfo['type'] = row[4]
            colInfo['order'] = row[5]
            table['cols'][row[3]] = colInfo

        return display_json(schemas, root='glue databases')

    def get_team_clusters(self, cluster_id=None):
        redshift = boto3.client('redshift')
        props = get_properties()
        if cluster_id == None:
            #clusters = redshift.describe_clusters(TagValues=[props['DATAMAKER_TEAM_SPACE']])['Clusters']
            payload = {
                'tag_values': [
                    props['DATAMAKER_TEAM_SPACE']
                ],
                'activity': 'describe_cluster'
            }
        else:
            #clusters = redshift.describe_clusters(ClusterIdentifier=cluster_id,)['Clusters']
            payload = {
                'cluster_identifier': cluster_id,
                'activity': 'describe_cluster'
            }
        clusters = self.apihelper.describe_cluster(payload)
        logger.info(f"cluster_response={clusters}")

        clusters_info = {}
        for cluster in clusters:
            cluster_id = cluster['ClusterIdentifier']
            cluster_model = {}
            cluster_model['cluster_id'] = cluster_id
            cluster_model['Name'] = cluster_id
            cluster_model['State'] = cluster['ClusterStatus']
            if 'Endpoint' in cluster:
                cluster_model['ip'] = f"{cluster['Endpoint']['Address']}:{cluster['Endpoint']['Port']}"

            cluster_nodes_info = {
                "node_type": cluster['NodeType'],
                "nodes": len(cluster['ClusterNodes'])
            }
            cluster_model['instances'] = cluster_nodes_info
            clusters_info[cluster_id] = cluster_model
            cluster_model['info'] = cluster
        return clusters_info


class AthenaUtils(DatabaseCommon):
    def get_connection_to_athena(self, DbName, region_name=None, S3QueryResultsLocation=None):
        workspace = get_workspace()
        if region_name == None:
            region_name = workspace['region']

        if S3QueryResultsLocation == None:
            S3QueryResultsLocation = f"s3://{workspace['scratch_bucket']}/athena"

        template_con_str = 'awsathena+rest://athena.{region_name}.amazonaws.com:443/' \
                           '{schema_name}?s3_staging_dir={s3_staging_dir}'
        conn_str = template_con_str.format(
            region_name=region_name,
            schema_name=DbName,
            s3_staging_dir=quote_plus(S3QueryResultsLocation))

        engine = create_engine(conn_str)
        self.db_url = conn_str
        self.current_engine = engine
        self.db_class = 'athena'
        return {
            'db_url': self.db_url,
            'engine': self.current_engine,
        }

    def getCatalog(self, database=None):
        glue = boto3.client('glue')
        schemas = dict()
        response = glue.get_tables(
            DatabaseName=database,
            MaxResults=1000
        )
        for t in response['TableList']:
            table = dict()
            schemas[t['Name']] = table
            table['name'] = t['Name']
            table['location'] = t['StorageDescriptor']['Location']
            table['cols'] = dict()
            for c in t['StorageDescriptor']['Columns']:
                col = dict()
                table['cols'][c['Name']] = col
                col['name'] = c['Name']
                col['type'] = c['Type']
        display_json(schemas, root="database")

        return display_json(schemas, root='glue databases')

