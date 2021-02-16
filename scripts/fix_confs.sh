#!/usr/bin/env bash

set -x 

cd ${1}

sed -i .bak "
s/name/Name/g;
s/codeartifact-domain/CodeartifactDomain/g;
s/codeartifact-repository/CodeartifactRepository/g;
s/eks-system-masters-roles/EksSystemMastersRoles/g;
s/scratch-bucket-arn/ScratchBucketArn/g;
s/user-pool-id/UserPoolId/g;
s/shared-efs-fs-id/SharedEfsFsId/g;
s/shared-efs-sg-id/SharedEfsSgId/g;
s/vpc-id/VpcId/g;
s/images/Images/g;
s/jupyter-hub/JupyterHub/g;
s/jupyter-user/JupyterUser/g;
s/-spark/-Spark/g;
s/landing-page/LandingPage/g;
s/code-build-image/CodeBuildImage/g;
s/repository/Repository/g;
s/source/Source/g;
s/path/Path/g;
s/version/Version/g;
s/networking/Networking/g;
s/data/Data/g;
s/internet-accessible/InternetAccessible/g;
s/nodes-subnets/NodesSubnets/g;
s/frontend/FrontEnd/g;
s/load-balancers-subnets/LoadBalancersSubnets/g;
s/teams/Teams/g;
s/instance-type/InstanceType/g;
s/local-storage-size/LocalStorageSize/g;
s/nodes-num-desired/NodesNumDesired/g;
s/nodes-num-max/NodesNumMax/g;
s/nodes-num-min/NodesNumMin/g;
s/policies/Policies/g;
s/grant-sudo/GrantSudo/g;
s/jupyterhub-inbound-ranges/JupyterhubInboundRanges/g;
s/plugins/Plugins/g;
s/efs-life-cycle/EfsLifeCycle/g;
s/profiles/Profiles/g;
s/id/Id/g;
s/module/Module/g;
s/parameters/Parameters/g;
" *.yaml