import logging
from ..common import get_properties
import pathlib
import subprocess
import os
import time
import sys
import socket
import requests
import boto3
import os
from os.path import expanduser,join
from .forward import forward
import json
from typing import Any, Optional, List, Dict, Union, Tuple

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger()
SSH_KEYPAIR_PATH = os.path.join(expanduser("~"), 'glue/ssh/')
SSH_KEYPAIR_FILENAME = 'glue_key'
UPDATE_DEV_ENDPOINT_TIMEOUT_SECONDS = 600
# String constants
PUBLIC_KEY = "PublicKey"
PUBLIC_KEYS = "PublicKeys"
DEV_ENDPOINT = "DevEndpoint"

glue_connections = {}


def remove_all_glue_public_keys(endpoint_name: Union[str, List[str]]) -> Any:
    """
    This API will remove all previously associated SSH Keys from the given endpoint.

    Note
    ----
    A glue endpoint support only 5 SSH keys.

    Parameters
    ----------
    endpoint_name: str
        A unique name for the Glue endpoint.

    Returns
    -------
    None
        None.

    Example
    -------
    >>> import aws.utils.notebooks.glue.endpoint as glue_connection
    >>> glue_connection.remove_all_glue_public_keys(endpoint_name=endpoint_name)
    """
    glue_client = boto3.client('glue')
    try:
        dev_endpoint = glue_client.get_dev_endpoint(EndpointName=endpoint_name)[DEV_ENDPOINT]
    except glue_client.exceptions.EntityNotFoundException:
        return

    public_keys_to_delete = list()
    if PUBLIC_KEY in dev_endpoint:
        public_keys_to_delete.append(dev_endpoint[PUBLIC_KEY])

    if PUBLIC_KEYS in dev_endpoint:
        for public_key in dev_endpoint[PUBLIC_KEYS]:
                public_keys_to_delete.append(public_key)
    _delete_public_keys(endpoint_name, public_keys_to_delete, glue_client)


def terminate_connection_to_glue(endpoint_name: Union[str, List[str]]) -> Any:
    """
    This API terminates the SSH connection to the Glue endpoint.

    Parameters
    ---------
    endpoint_name: list
         A unique name for the Glue endpoint.

    Returns
    -------
    None
        None.

    Example
    -------
   >>> import aws.utils.notebooks.glue.endpoint as glue_connection
   >>> glue_connection.terminate_connection_to_glue(endpoint_name)
    """
    if endpoint_name in glue_connections:
        glue_conn = glue_connections[endpoint_name]
        glue_conn['shh_fwd_tunnel'].shutdown()
        del glue_connections[endpoint_name]
        _delete_old_ssh_public_key_if_associated(endpoint_name=endpoint_name,hostname=socket.gethostname(), glue_client = boto3.client('glue'))
    else:
        raise Exception("Connection to endpoint {} not found".format(endpoint_name))


def connect_to_glue(
        endpoint_name: Union[str, List[str]],
        reuse: Optional[bool] = True,
        start: Optional[bool] = False,
        args: Optional[dict] = dict()
) -> Union[Tuple[Any, Any], Tuple[str, bool]]:
    """
    This API creates a connection to a glue endpoint , and can also create the glue endpoint itself if one does not
    exists. The API returns livy URL that can be used to start Spark sessions with Python, SQL and Scala and support
    the Glue dynamic Frame.

    Parameters
    ---------
    endpoint_name: lst
      A unique name for the Glue endpoint
    reuse: optional, bool, default: True
       if reuse is True and endpoint exists , will reuse the existing endpoint
    start: optional, bool, default: False
      if start is True and cannot re-use endpoint, then will start a new endpoint
    args: optional, dict
      Optional list of arguments to control the Glue endpoint definition used to start the new endpoint.

    Returns
    -------
    livy_url : str
        The livy url to use for starting the spark session
    started : bool
        True if a new endpoint was started in this call

    Example
    ------
    >>> import aws.utils.notebooks.glue.endpoint as glue_connection
    >>> (livy_url, started) =  glue_connection.connect_to_glue(endpoint_name=clusterName,
    ...                                                             reuse=True,
    ...                                                             start=True,
    ...                                                             args={"dpus" :2})
    """
    if endpoint_name in glue_connections:
        glue_conn = glue_connections[endpoint_name]
        return (glue_conn['conn'],glue_conn['started'])

    props = get_properties()
    hostname = socket.gethostname()
    glue_client = boto3.client('glue')
    (endpoint,started) = _get_glue_endpoint(glue_client, start, endpoint_name, args)

    # At this point we have and endpoint

    # 1.  Lets make sure the endpoint has our SSH public key
    (new_key_generated,key_path) = _generate_ssh_keypair(hostname)
    if new_key_generated or not _is_ssh_public_key_associated(endpoint, hostname):
        _associate_keypair_with_dev_endpoint(endpoint_name, glue_client)

    # 2. Now we need to start the SSH tunneling
    logger.info(endpoint)
    dev_endpoint_address = endpoint['PrivateAddress'] if 'PrivateAddress' in endpoint else endpoint['PublicAddress']
    print("Starting SSH connection with Glue Endpoint")
    (shh_fwd_tunnel,local_port) = forward(dev_endpoint_address, '169.254.76.1', key_path)

    conn = "http://localhost:{}".format(local_port)

    glue_connections[endpoint_name] = {
        "conn": conn,
        "shh_fwd_tunnel" : shh_fwd_tunnel,
        "started" : started
    }
    print("Connection Established")

    return (conn, started)


def create_glue_endpoint(
        endpoint_name: Union[str, List[str]],
        args: Optional[Dict[str, Any]] = {}
) -> Dict[str, Any]:
    """
    This API creates a glue endpoint accessible only for this role.

    Parameters
    ---------
    endpoint_name : list
        A unique name for the Glue endpoint
    args : optional, dict
        Optional list of arguments to control the Glue endpoint definition used to start the new endpoint

    Returns
    --------
    response: dict
        A DevEndpoint definition for the newly created one.

    Example
    ------
    >>> import aws.utils.notebooks.glue.endpoint as glue_connection
    >>> glue_connection.create_glue_endpoint(endpoint_name=endpoint_name, args={"dpus" :2})
    """

    glue_client = boto3.client('glue')
    return _create_glue_endpoint(glue_client,endpoint_name,args)


def _create_glue_endpoint(
        glue_client: boto3.client('glue'),
        endpoint_name: Any,
        args: Any
) -> Any:
    """
    Helps create a glue endpoint accessible for this users role.
    """
    if 'dpus' not in args:
        logger.info("'dpus' parameter is not specified , starting endpoint with default 2 dpus")
        args['dpus'] = 2

    props = get_properties()

    lambda_client = boto3.client('lambda')
    env = props['AWS_DATAMAKER_ENV']
    team_space = props['DATAMAKER_TEAM_SPACE']
    start_glue_lambda_name = f'datamaker-{env}-{team_space}-StartGlueEndpoint'

    ExtraPythonLibsS3Path = args['ExtraPythonLibsS3Path'] if 'ExtraPythonLibsS3Path' in args else ''

    ExtraJarsS3Path =  args['ExtraJarsS3Path'] if 'ExtraJarsS3Path' in args else ''

    invoke_response = lambda_client.invoke(
        FunctionName=start_glue_lambda_name,
        Payload=bytes(json.dumps({"endpoint_name": endpoint_name, "dpus": args['dpus'], "ExtraPythonLibsS3Path": ExtraPythonLibsS3Path, "ExtraJarsS3Path":ExtraJarsS3Path }), "utf-8"),
        InvocationType='RequestResponse',
        LogType='Tail'
    )

    time.sleep(2)

    response = glue_client.get_dev_endpoint(
        EndpointName=endpoint_name
    )

    while response['DevEndpoint']['Status'] == 'PROVISIONING':
        logger.info("provisioning endpoint %s", endpoint_name)
        time.sleep(30)
        response = glue_client.get_dev_endpoint(
            EndpointName=endpoint_name
        )

    return response['DevEndpoint']


def _get_glue_endpoint(
        glue_client: boto3.client('glue'),
        start: Any,
        endpoint_name: Any,
        args: Any
) -> Tuple[Any, bool]:
    """
    Get Dev endpoint or starts a new one and returns endpoint with True if a new endpoint is created.
    """
    try:
        glue_ep = glue_client.get_dev_endpoint(EndpointName=endpoint_name)['DevEndpoint']
        return (glue_ep, False)
    except:
        if not start:
            raise Exception("cannot find running glue endpoint {}, and start=False: ".format(endpoint_name))
        else:
            glue_ep = _create_glue_endpoint(glue_client, endpoint_name, args)
            return (glue_ep,True)


def delete_glue_endpoint(endpoint_name: Union[str, List[str]]) -> None:
    """
    Deletes glue endpoint

    Parameter
    ---------
    endpoint_name: list
        A unique name for the Glue endpoint

    Returns
    ------
    None
        None.

    Example
    -------
    >>> import aws.utils.notebooks.glue.endpoint as glue_connection
    >>> glue_connection.delete_glue_endpoint(endpoint_name=endpoint_name)
    """
    glue_client = boto3.client('glue')
    logger.info("deleting endpoint %s", endpoint_name)
    response = glue_client.delete_dev_endpoint(
        EndpointName=endpoint_name
    )


def _generate_ssh_keypair(hostname: Any) -> Tuple[bool, str]:
    """
    Generates a SSH key-pair ifo ne not already created and  make sure the endpoint has our SSH public key by returning
    the SSH key-path.
    """
    logger.info("Key directory: " + SSH_KEYPAIR_PATH)

    keyPath = SSH_KEYPAIR_PATH + SSH_KEYPAIR_FILENAME
    if os.path.exists(SSH_KEYPAIR_PATH):
        logger.info("SSH key pair is already created")
        return (False,keyPath)

    pathlib.Path(SSH_KEYPAIR_PATH).mkdir(parents=True)

    cmd = ['/usr/bin/ssh-keygen', '-m','PEM','-f', keyPath, '-t', 'rsa', '-C',
                                   hostname, '-N', '']

    logger.debug("Generating SSH key pair for %s" ,hostname)
    logger.debug(' '.join(cmd))

    print(subprocess.check_output(cmd))

    os.chmod(keyPath, 0o0400)

    if not os.path.exists(keyPath):
        raise Exception("SSH Key was not created")

    return (True,keyPath)


def _associate_keypair_with_dev_endpoint(
        dev_endpoint_name: Any,
        glue_client: boto3.client('glue')
) -> None:
    """
    This API associates the SSH Key-pair we generated with our Dev Endpoint.
    """
    print("Associating SSH public key with dev endpoint...")
    with open(SSH_KEYPAIR_PATH + SSH_KEYPAIR_FILENAME + ".pub", 'r') as f:
        public_key = f.read()

    glue_client.update_dev_endpoint(EndpointName=dev_endpoint_name, AddPublicKeys=[public_key])
    _wait_for_dev_endpoint_update_complete(dev_endpoint_name, glue_client)


def _is_ssh_public_key_associated(
        dev_endpoint: Any,
        hostname: Any
) -> bool:
    """
    Returns a boolean whether or not SSH public key is associated to a dev endpoint.
    """
    if PUBLIC_KEYS in dev_endpoint:
        for public_key in dev_endpoint[PUBLIC_KEYS]:
            if hostname in public_key:
                return True
    logger.debug('cannot find key for %s <-> %s', dev_endpoint, hostname)
    return False


def _delete_old_ssh_public_key_if_associated(
        endpoint_name: Any,
        hostname: Any,
        glue_client: boto3.client('glue')
) -> None:
    """
    Deletes old SSH public keys if they are associated with the dev endpoint.
    """
    dev_endpoint = glue_client.get_dev_endpoint(EndpointName=endpoint_name)[DEV_ENDPOINT]
    public_keys_to_delete = list()
    if PUBLIC_KEY in dev_endpoint:
        public_keys_to_delete.append(dev_endpoint[PUBLIC_KEY])

    if PUBLIC_KEYS in dev_endpoint:
        for public_key in dev_endpoint[PUBLIC_KEYS]:
            if hostname in public_key:
                public_keys_to_delete.append(public_key)
    _delete_public_keys(endpoint_name, public_keys_to_delete, glue_client)


def _delete_public_keys(
        dev_endpoint_name: Any,
        public_keys_to_delete: Any,
        glue_client: boto3.client('glue')
) -> None:
    """
    Waits for previous updates on dev endpoint, then deletes previously associated public keys specified if they exist.
    """
    # dev endpoint doesn't allow concurrent update. Therefore wait for previous update to complete if any
    _wait_for_dev_endpoint_update_complete(dev_endpoint_name, glue_client)
    if public_keys_to_delete:
        print("Deleting previously associated public keys from dev endpoint..")
        glue_client.update_dev_endpoint(EndpointName=dev_endpoint_name, DeletePublicKeys=public_keys_to_delete)
        _wait_for_dev_endpoint_update_complete(dev_endpoint_name, glue_client)
        print('Successfully deleted previously associated public keys')
    else:
        print("No previously associated public keys to delete from dev endpoint..")


def _wait_for_dev_endpoint_update_complete(
        dev_endpoint_name: Any,
        glue_client: boto3.client('glue')
) -> None:
    """
    Waits for dev endpoint update to complete before moving on.
    """
    start = time.time()
    while time.time() - start < UPDATE_DEV_ENDPOINT_TIMEOUT_SECONDS:
        print('Waiting for DevEndpoint update to complete...')
        time.sleep(5)
        dev_endpoint = glue_client.get_dev_endpoint(EndpointName=dev_endpoint_name)[DEV_ENDPOINT]
        if 'LastUpdateStatus' not in dev_endpoint:
            break
        if dev_endpoint['LastUpdateStatus'] == 'COMPLETED':
            print('Successfully updated dev endpoint')
            break
        elif dev_endpoint['LastUpdateStatus'] == 'FAILED':
            print('Update dev endpoint failed. Exiting...')
            sys.exit(1)


def _ping_livy() -> None:
    """
    Ping livy to see if you can reach it.
    """
    print("Pinging Livy...")
    requests.get(url = "http://localhost:8998")
    print("Successfully pinged Livy")
