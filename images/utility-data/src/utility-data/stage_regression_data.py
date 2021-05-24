#!/usr/bin/env python3

import json
import subprocess
import sys

import boto3


def main() -> None:
    if len(sys.argv) == 2:
        env_name = sys.argv[1]
    else:
        raise ValueError("Orbit environment name required")
        sys.exit(1)
    try:
        ssm = boto3.client("ssm")
        b_name = f"/orbit/{env_name}/demo"
        d_c = json.loads(ssm.get_parameter(Name=b_name)["Parameter"]["Value"])
        lake_bucket = d_c.get("LakeBucket").split(":::")[1]

        prefix_cms = "landing/data/cms/"
        prefix_sm = "landing/data/sagemaker/"
        prefix_cms_schema = "landing/cms/schema/"

        local_cms = "/opt/orbit/data/cms"
        local_sm = "/opt/orbit/data/sagemaker"
        local_schema = "/opt/orbit/cms/schema"

        print(f"Uploading regression data to s3://{lake_bucket}/{prefix_cms}")
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                local_cms,
                "s3://" + lake_bucket + "/" + prefix_cms,
                "--recursive",
            ]
        )

        print(f"Uploading sagemaker data to s3://{lake_bucket}/{prefix_sm}")
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                local_sm,
                "s3://" + lake_bucket + "/" + prefix_sm,
                "--recursive",
            ]
        )

        print(f"Uploading schema to s3://{lake_bucket}/{prefix_cms_schema}")
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                local_schema,
                "s3://" + lake_bucket + "/" + prefix_cms_schema,
                "--recursive",
            ]
        )

    except Exception as ex:
        print(ex)
        sys.exit(1)


if __name__ == "__main__":
    main()
