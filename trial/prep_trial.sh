#!/bin/bash


rm -f trial.zip

zip trial.zip -j add_user.py \
    buildspec.yaml \
    ../samples/manifests/trial/demo-lake-admin-cfn-template.yaml \
    ../samples/manifests/trial/demo-lake-creator-cfn-template.yaml \
    ../samples/manifests/trial/demo-lake-user-cfn-template.yaml \
    ../samples/manifests/trial/lake-admin-plugins.yaml \
    ../samples/manifests/trial/lake-creator-plugins.yaml \
    ../samples/manifests/trial/lake-user-plugins.yaml \
    ../samples/manifests/trial/trial-manifest.yaml


buckets="aws-orbit-workbench-public-us-east-1 \
         aws-orbit-workbench-public-us-east-2 \
         aws-orbit-workbench-public-us-west-1 \
         aws-orbit-workbench-public-us-west-2 \
         aws-orbit-workbench-public-eu-west-1 "

for bucket in $buckets; do
    echo $bucket
    aws s3 cp trial.zip s3://$bucket/deploy/trial.zip
    aws s3 cp trial_pipeline_cfn.yaml s3://$bucket/deploy/trial_pipeline_cfn.yaml
    aws s3 cp buildspec.yaml s3://$bucket/deploy/buildspec/buildspec.yaml
done

