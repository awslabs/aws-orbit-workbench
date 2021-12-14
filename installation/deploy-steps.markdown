---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Deploy AWS Orbit Workbench
permalink: deploy-steps
---

# Steps to Deploy AWS Orbit Workbench 
This page outlines the steps to deploy an AWS Orbit Workbench.  The workbench source code is found in
the [AWS Labs github repository](https://github.com/awslabs/aws-orbit-workbench/).
<br><br>
Some of these steps (as indicated) will only need to be run once, others can be run multiple times in order to update the deployment.  

<br><br>
**_IMPORTANT_** <br>The workbench uses a manifest to define componenents of the infrastructure.  The manifest is in YAML format.<br>
Please see the full list of elements in a [manifest](orbit-manifest-guide) for reference.  
<br>
## Steps Outline

#### Dependancies
- Python 3.7 (recommended)

----
### Outline

1.   Clone [AWS Labs github repository](detail-fork)
2.   Install the [CLI](detail-cli)
     - _only once_
3.   Install [AWS CodeSeeder](detail-codeseeder) 
     - _only once_
4.   Generate a new [manifest](detail-manifest) 
     - _once created, you will add / remove from this manifest as your platform changes_
5.   Deploy a new [foundation](detail-foundation) 
     -  _you may have an existing foundation (VPC, Subnets, EFS, and Cognito) that can be leveraged_
     -  **_this is OPTIONAL if you have the necessary components_**
6.   Deploy a new [toolkit](detail-toolkit) 
     - _only once_
7.   Deploy [credentials](detail-credentials) 
     - _only once_
     -  **_this is OPTIONAL_**
8.   Deploy [docker images](detail-images) 
     - _once deployed, you may deploy one or all the base workbench images as needed_
9.   Deploy [environment](detail-environment)
     - _only once, but can be rerun to update an existing environment_
10.  Deploy [teams](detail-teams)
     - _you may run this repeatedly to update teams or plugins_


