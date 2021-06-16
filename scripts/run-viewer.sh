#!/bin/bash

set -e

aws eks update-kubeconfig --alias $ORBIT_ENV_NAME --region $REGION --name orbit-$ORBIT_ENV_NAME --role-arn arn:aws:iam::`aws sts get-caller-identity --query Account --output text`:role/orbit-$ORBIT_ENV_NAME-admin
kubectl proxy --accept-hosts '.*' --context $ORBIT_ENV_NAME &
docker run -it -p 8080:8080 -e CLUSTERS=http://docker.for.mac.localhost:8001 hjacobs/kube-ops-view