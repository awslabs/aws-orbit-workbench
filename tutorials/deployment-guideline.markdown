---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Deployment Guideline
permalink: deployment-guideline
---


### Deploying foundation (optional)

Deploying foundation is required only if your AWS account does not have the prerequisites required
for creating the Orbit environment as listed below. Our foundation deployment can deploy required resources
such as VPC, S3 Bucket, Cognito, EFS FileSystem, VPC Endpoints and more to allow quick experimentation with Orbit.  However, it is not recommended
for production accounts, where more AWS Well-Architected controls should be deployed per your company needs.

#### Prerequisites

1. Create and activate a Python virtual environment for the CLI
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Orbit CLI tool should be installed  
   ```
   $ pip install aws-orbit
   ```   

3. Access to an AWS account with an IAM role that has at least the permissions to deploy the foundation and cdk tool kit resources.   

4. Download the demo directory from the orbit source bundle, which contains sample manifest files used in this walk through.
   ```
   $ curl -L -o orbit.zip https://github.com/awslabs/aws-orbit-workbench/archive/main.zip
   $ unzip orbit.zip
   $ cd aws-orbit*/samples/manifests/demo
   ```   
5. Create a CodeArtifact Domain and Repository using the below helper script
   ```
   /scripts/init_codeartifact.sh
   ```

**IMPORTANT: If you want to allow access to internet from your environment, and do not have security concern with this , you should deploy the foundation using step B, otherwise use step A which will deploy isolated subnets and a set of VPC endpoints to allow secured access to AWS services (There are limitations on where these can be deployed base on supported regions for the VPC endpoints).**

A) Deploying Foundation without internet access
   ```
   $ orbit deploy foundation -n dev-env --no-internet-accessibility
   ```       

   --------  OR --------

B) Deploying Foundation with internet access
   ```
   $ orbit deploy foundation -n dev-env --internet-accessibility
   ```     

> Note: Feel free to use `--debug` for orbit commands during deployment.   

### Deploying new environment
#### Prerequisites   
> Note: If the orbit foundation is not deployed, we should make sure that the below resources exist as a part of our environment
1. VPC with public as well as private\isolated subnets (interface endpoints in case of isolated subnets).
2. An S3 bucket for scratch data used by the various teams
3. An EFS filesystem that will be access by all teams. Each team has dedicated isolated folder.
4. KMS Key
5. Cognito UserPool
6. If you are deploying on isolated subnets (internet accessible=False), VPC endpoints must be created and associated with the subnets.

#### Deploying the environment

After defining a deployment manifest (see [Example Manifest that works with foundation only](https://raw.githubusercontent.com/awslabs/aws-orbit-workbench/main/samples/manifests/demo/manifest.yaml)), run the following command:
This command deploys your environment that includes the EKS cluster and all other shared resources required for
your teams to operate.  
   ```
   $ orbit deploy env -f manifest.yaml
   ```    

It can take about 1 hour to deploy your environment which can vary base on your node pools definitions.

### Deploying new teams
#### Prerequisites

1. An Existing Orbit Environment
2. Cloudformation file defining any additional resources or policies required by your teams.
3. List of default container profiles for each team use. (see profiles in [Example Manifest](example_manifest.yaml)))
4. Installing the plugins under [Built in plugins](https://github.com/awslabs/aws-orbit-workbench/wiki/plugins)

#### Deploying teams

At any time, you can update your environment manifest and add new teams, or remove obsolete ones.
The following command will create the new teams:
   ```
   $ orbit deploy teams -f manifest.yaml
   ```   

It can take about 10-30 min to deploy your team which can vary base on your team configurations.


#### Destroying your team(s)   
```
$ orbit destroy teams -e dev-env
```

#### Destroying a environment   
```
$ orbit destroy env -e dev-env
```
#### Destroying a foundation   
```
$ orbit destroy foundation --name dev-env
```
