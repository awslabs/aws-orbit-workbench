""" Module to deploy self signed certs and upload it to IAM """
import logging
import subprocess
from typing import cast

import boto3
from botocore.exceptions import ClientError

from aws_orbit.models.context import FoundationContext

_logger: logging.Logger = logging.getLogger(__name__)


def run_command(cmd: str) -> str:
    """Module to run shell commands."""
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, timeout=3, universal_newlines=True)
    except subprocess.CalledProcessError as exc:
        _logger.debug("Command failed with exit code {}, stderr: {}".format(exc.returncode, exc.output.decode("utf-8")))
        raise Exception(exc.output.decode("utf-8"))
    return output


def check_cert(context: "FoundationContext") -> str:
    ssl_cert_arn: str = cast(str, context.networking.frontend.ssl_cert_arn)
    if ssl_cert_arn:
        return ssl_cert_arn
    else:
        return deploy_selfsigned_cert(context)


def deploy_selfsigned_cert(context: "FoundationContext") -> str:
    """Module to deploy self signed cert"""

    _logger.debug("Generating self-signed certificate...")

    _logger.debug("Creating private key...")
    convert_key: str = "openssl genrsa 2048 > private.pem"
    run_command(cmd=convert_key)

    _logger.debug("Creating Certificate signing request...")
    generate_csr: str = (
        "openssl req -new -key private.pem "
        "-out csr.pem "
        '-subj "/C=US/ST=SEA/L=SEA/O=AWSOrbit Security/OU=AWSOrbit Department/CN=AWSOrbit"'
    )
    run_command(cmd=generate_csr)

    _logger.debug("Creating Public certificate...")
    generate_pub: str = "openssl x509 -req -days 365 -in csr.pem " "-signkey private.pem -out public.pem "
    run_command(cmd=generate_pub)

    with open("private.pem", "r") as fp:
        private_pem = fp.read()

    with open("public.pem", "r") as fp:
        public_pem = fp.read()

    _logger.debug("Uploading the cert to IAM...")
    ssl_cert_arn = upload_cert_iam(context, private_pem, public_pem)
    return ssl_cert_arn


def upload_cert_iam(context: "FoundationContext", private_pem: str, public_pem: str) -> str:
    """Uploads the cert to AWS IAM"""
    iam_client = boto3.client("iam")
    ssl_cert_name = f"{context.name}-{context.region}"
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
