""" Module to deploy self signed certs and upload it to IAM """
import logging
import subprocess
from typing import cast

import boto3
from botocore.exceptions import ClientError

_logger: logging.Logger = logging.getLogger(__name__)


def run_command(cmd: str) -> str:
    """ Module to run shell commands. """
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, timeout=3, universal_newlines=True)
    except subprocess.CalledProcessError as exc:
        _logger.debug("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output.decode("utf-8")))
        raise Exception(exc.output.decode("utf-8"))
    return output


def deploy_selfsigned_cert() -> str:
    """ Module to deploy self signed cert """

    _logger.debug("Generating self-signed certificate...")
    generate_cert: str = (
        "openssl req -x509 -nodes -days 365 -newkey rsa:2048 "
        "-keyout privateKey.key -out certificate.crt "
        '-subj "/C=US/ST=SEA/L=SEA/O=AWSOrbit Security/OU=AWSOrbit Department/CN=AWSOrbit"'
    )
    run_command(cmd=generate_cert)

    _logger.debug("Converting the key into .pem file...")
    convert_key: str = "openssl rsa -in privateKey.key -text > private.pem"
    run_command(cmd=convert_key)
    with open("private.pem", "r") as fp:
        private_pem = fp.read()

    _logger.debug("Converting the cert into .pem file...")
    convert_pem: str = "openssl x509 -inform PEM -in certificate.crt > public.pem"
    run_command(cmd=convert_pem)
    with open("public.pem", "r") as fp:
        public_pem = fp.read()

    _logger.debug("Uploading the cert to IAM...")
    ssl_cert_arn = upload_cert_iam(private_pem, public_pem)
    return ssl_cert_arn


def upload_cert_iam(private_pem: str, public_pem: str) -> str:
    """ Uploads the cert to AWS IAM """
    iam_client = boto3.client("iam")
    ssl_cert_name = "AWSORBIT"
    try:
        response = iam_client.get_server_certificate(ServerCertificateName=ssl_cert_name)
        return cast(str, response["ServerCertificate"]["ServerCertificateMetadata"]["Arn"])
    except ClientError as ex:
        if ex.response["Error"]["Code"] == "NoSuchEntity":
            response = iam_client.upload_server_certificate(
                ServerCertificateName=ssl_cert_name, CertificateBody=public_pem, PrivateKey=private_pem
            )
            return cast(str, response["ServerCertificateMetadata"]["Arn"])
        else:
            raise ex
