#!/bin/bash

set -e

if [[ -z "$ORBIT_ENV_NAME" ]]; then
    echo "Must provide ORBIT_ENV_NAME in environment" 1>&2
    exit 1
fi

orbit replicate image -e ${ORBIT_ENV_NAME} --source_registry dockerhub --source_repository hjacobs/kube-ops-view  --source_version 20.4.0 --name kube-ops-view
helm install stable/kube-ops-view --version 1.2.1 --generate-name \
--set image.repository=495869084367.dkr.ecr.us-west-2.amazonaws.com/orbit-dev-env/users/kube-ops-view \
--set service.type=LoadBalancer \
--set nodeSelector.orbit/node-group=env \
--set nodeSelector.orbit/usage=reserved \
--version 1.2.4 \
--set rbac.create=True \
--namespace env


host = kubectl get svc -n env -l app.kubernetes.io/name=kube-ops-view -o json | jq -r '.items[0].status.loadBalancer.ingress[0].hostname'
echo "USE THIS URL https:/$host"