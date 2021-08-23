---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Orbit Manifest Guide
permalink: orbit-manifest-guide
---

### Structure

Orbit Manifest allow administrators to quickly deploy Orbit environments and integrate them
with existing AWS account resources.

The following manifest example explain the basic structure of a manifest:

```yaml

Name: # Name of the Orbit Environment .
CodeartifactDomain: # The code artifact domain name used to load Python packages by Orbit
CodeartifactRepository: # The code artifact repository used to load Python packages by Orbit
EksSystemMastersRoles:
-   # Any additional IAM roles that should be EKS Admin
ScratchBucketArn: # The S3 bucket that will be access by all teams. Each team has dedicated isolated folder.
UserPoolId: # The Cognito user pool id for controlling access to Orbit
SharedEfsFsId: # The EFS filesystem ID that will be access by all teams. Each team has dedicated isolated folder.
SharedEfsSgId: # The security group ID that controls access to the EFS.
Networking:
    VpcId: # your vpc-id
    PublicSubnets: # list of public subnets
    PrivateSubnets: # list of private subnets
    IsolatedSubnets: # list of isolated subnets
    Data:
        InternetAccessible: # true/false if you allow teams to access internet through their notebooks
        NodesSubnets: # list of subnets where your EKS nodes should be created
    Frontend:
        LoadBalancersSubnets: # list of subnets where your front end load balancers should be created
        SslCertArn: # Provide a reference to an SSL Cert   
        CustomDomainName: # Conditionally required to integrate a DNS name to the custom created SSLCert
ManagedNodegroups:
# define here your EKS node pools
-   Name: primary-compute # A general compute node pool used for simple ETL
    InstanceType: m5.2xlarge
    LocalStorageSize: 128
    NodesNumDesired: 4
    NodesNumMax: 4
    NodesNumMin: 1
    Labels:
        instance-type: m5.2xlarge
-   Name: primary-gpu # A GPU-based node pool used for ML training jobs
    InstanceType: g4dn.2xlarge
    LocalStorageSize: 128
    NodesNumDesired: 2
    NodesNumMax: 3
    NodesNumMin: 1
Teams:
# define here your Teams.  You can continue adding (or removing) teams as needed
-   Name: # provide here the name of the team
    Policies: # Provide IAM policy names to add permission to any additional non-orbit cloud resources
    - # iam policy name 1
    GrantSudo: true # Will the team users be allow to sudo
    Fargate: false # Will the team users have access to Fargate to run containers
    K8Admin: true # Will the team users be admin of the EKS Cluster
    JupyterhubInboundRanges: # Control the ingress access to JupyterHub
    - 0.0.0.0/0
    Profiles:
    # List of default profiles to define containers
    - display_name: Nano # Defining a small container for quick look
      slug: nano
      description: 1 CPU + 1G MEM
      kubespawner_override:
          cpu_guarantee: 1
          cpu_limit: 1
          mem_guarantee: 1G
          mem_limit: 1G
    - display_name: Small (GPU Enabled) # Defining a container with GPU requirement and custom image
      slug: small-gpu
      description: 2 CPU + 4G MEM + 1 GPU
      kubespawner_override:
          image: "*****.dkr.ecr.us-west-2.amazonaws.com/my_custome_image"
          cpu_guarantee: 2
          cpu_limit: 2
          mem_guarantee: 4G
          mem_limit: 4G
          extra_resource_limits:
              nvidia.com/gpu: '1'
          extra_resource_guarantees:
              nvidia.com/gpu: '1'

    Plugins:
    # Using plugins to extend Orbit Teams deployment with additional functionality
    # <The following plugin will launch a POD on team creation to clean up a certain directory>
    - PluginId: team_script_launcher # The plugin id
      Module: team_script_launcher # The Plugin python module name
      Path: ../plugins/team_script_launcher/ # Path to the plugin module code
      Parameters: # Set of parameters
          script: |
              i=0
              while [ $i -lt 1 ];
              do
                find /efs/shared/regression -mtime +5 -exec rm {} \;
                sleep 60
              done
              echo "DONE LOOP"
          restartPolicy: Never

```

[Here](https://github.com/awslabs/aws-orbit-workbench/tree/main/samples/manifests/demo) is a pointer to the location of sample plugin definitions per teamspace from Orbit samples.   

## Properties     

***   

#### Networking   

Orbit's deployment needs underlying networking resources support. Customer can deploy Orbit foundation which provides the required networking resources, but if the customer is planning on using existing networking resources, they should consider providing the `physical_id(s)` of their respective resources or the location of SSM parameter which has them.    

***Required***: `Optional`    

***   

#### SslCertArn   

The default behavior is Orbit framework will create a self signed certificate and integrate with the ALB.
> Syntax: !SSM ${/orbit-f/demo-fndn/resources::SslCertArn}   

If you would like to provide an externally created SSL Certificate, below is the syntax.   
> Syntax: "arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012"



***Required***: `Optional`

***   

#### ManagedNodegroups   

Once we have the necessary networking support, Orbit's platform needs compute capacity for running workloads. AWS Orbit leverages AWS Elastic Container Service for Kubernetes and `ManagedNodegroups` attribute helps customers declare a list of hybrid style of managed worker nodes based on their workloads.    

***Required***: `Required`    

***   

#### Teams   

`Teams` attribute correspond to an actual team in any Enterprise, where a customer can mention a list of their data teams who wants to leverage Orbit platform. For every team that is mentioned in the manifest file, there is a corresponding `Cognito UserGroup` created.   

***Required***: `Required`    

***   

### YAML Syntax Enhancements

#### 1. System environment variables support

You can parameterize your manifests using system environment variables as follow:

```
name:  "!ENV {ORBIT_ENV_NAME::dev-env}"
```

If the ORBIT_ENV_NAME is defined as env variable in your shell,  then the value of this variable is used for the property 'name', otherwise a default value of 'dev-env' is used.

#### 2. AWS System Manager Parameter support

You can parameterize your manifests using AWS SSM parameters as follow:

```
ScratchBucketArn:  "!SSM ${/orbit-foundation/dev-env/resources::ScratchBucketArn}"
```

The value of the '' would be defined by fetching the value of the SSM parameter named '/orbit-foundation/dev-env/resources' and then retrieving the value of the JSON path 'ScratchBucketArn'.  For example, if your SSM parameter contains this structure:
```json
{
  "ScratchBucketArn": "arn://xxxxx"
}
```
The value of 'ScratchBucketArn' will be "arn://xxxxx"


#### 3. Breaking the manifest into multiple files

When your manifest grows over time, or when you want to reuse similar structure for different teams, you can use other files. For example, using the following instruction, we can use a set of plugins that are defined in a common plugin.yaml file:

```yaml
    Plugins: !include lake-creator-plugins.yaml
```

You can include other 'yaml' or 'json' files.
