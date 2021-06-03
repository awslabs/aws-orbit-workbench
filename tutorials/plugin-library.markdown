---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Plugin Library
permalink: plugin-library
---
##  Orbit Plugin Definiton and Configuration
Orbit plugins are individual python modules published PyPi.  We are continually adding plugin capabilites to the platform.  This is the current list of published plugins:
 - [Amazon Redshift Plugin](#rs_plugin)
 - [AWS Code Commit Plugin](#codecommit_plugin)
 - [Custom AWS Cloudformation Plugin](#cfn_plugin)
 - [EMR on EKS Plugin](#emreks_plugin)
 - [Lustre Plugin](#lustre_plugin)
 - [Ray Plugin](#ray_plugin)
 - [SageMaker-Operators for K8s Plugin](#sm_operator_plugin)
 - [Team Script Launcher Plugin](#ts_plugin)
 - [Overprovisioning Plugin](#op_plugin)

Each Plugin has a configuration that you need to define.  The structure is as follows (in yaml format):

```
- PluginId: <the name of the plugin>
  Module: <the module name>
  Path: <relative path of plugin src code>
  Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
```
*PluginId* - a unique idetnifier for the plugin

*Module* - the name of the module (get this from the examples below for your plugin)

*Path* - the relative path of the src code for the plugin (relative to the cli/ directory)

*Parameters* - configurable plugin-specific parameters 

The plugin configurations are located in a yaml configuration file that is referenced in the manifest.  For example, the [lake-creator plugin](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/manifests/demo/lake-creator-plugins.yaml) declares the plugin requirement for a team defined in [lake-creator team](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/manifests/demo/manifest.yaml#L41). In this example, the individual plugins are defined in [lake-creator plugin](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/manifests/demo/lake-creator-plugins.yaml).  Adding or remvoing plugin definitions effectively adds or removes the plugin deployment from your environment when deployed.  The [lake-creator plugin](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/manifests/demo/lake-creator-plugins.yaml) references these plugin definitions in the teams section.

----
### <a name="rs_plugin">Amazon Redshift </a>
This plugin configures redshift cluster creation, accessiblity and termination capabilities using Orbit SDK [helper methods](https://github.com/awslabs/aws-orbit-workbench/blob/main/sdk/aws_orbit_sdk/database.py). Before deleting teamspaces, recommended approach is to do gracefull terminate of all teamspace specific redshift clusters. While destroying teamspace, left over redshift clusters are terminated forcibly by design.
```
- PluginId: 
  Module: 
  Path: ../plugins/redshift/
  Parameters:
    enable_user_activity_logging: "true"
    require_ssl: "true"
    use_fips_ssl: "true"
    node_type: "DC2.large"
    number_of_nodes: "2"
```
#### Parameters 
- *enable_user_activity_logging* - Enable [database audit logging](https://docs.aws.amazon.com/redshift/latest/mgmt/db-auditing.html)
- *require_ssl* - Enable SSL security. [Configuring security options for connections.](https://docs.aws.amazon.com/redshift/latest/mgmt/connecting-ssl-support.html)
- *use_fips_ssl* - Enable FIPS-compliant SSL mode only if your system is required to be FIPS-compliant.
- *node_type* - Default value for the required cluster node type. [Supported types.](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-clusters.html#working-with-clusters-overview)
- *number_of_nodes* - Default value for the required number of nodes in the cluster.

References:
- [Amazon Redshift](https://docs.aws.amazon.com/redshift/index.html)

----
### <a name="codecommit_plugin">AWS Code Commit </a>
This plugin enables Orbit users to have access to an AWS Code Commit repository.
```
- PluginId: code_commit
  Module: code_commit
  Path: ../plugins/code_commit/ 
```
#### Parameters 
*None*

References
- [AWS CodeCommit](https://docs.aws.amazon.com/codecommit/latest/userguide/welcome.html)

----

### <a name="cfn_plugin">AWS Cloudformation </a>
This plugin enables the execution of a custom AWS Cloudformation template.
```
- PluginId: 
  Module: 
  Path: ../plugins/custom_cfn/
  Parameters:
    - CfnTemplatePath: "./bundle/plugins/demo-lake-user-cfn-template.yaml"   
```

#### Parameters 
 - *CfnTemplatePath* - this defines where the template to be executed is located.  Orbit creates a 'bundle' of all code to be deployed.  In the example above, the path specifies a template that is in the 'bundle' at the same level as the manifests - [demo-lake-user-cfn-template.yaml](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/manifests/plugins/demo-lake-user-cfn-template.yaml)

References: 
- [AWS Cloudformation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html)

----
### <a name="emreks_plugin">EMR on EKS </a>
This plugin enables the orbit workspace to interact and submit spark jobs to EKS.  Please see [here](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/notebooks/B-DataAnalyst/Example-3-Spark-EMR-on-EKS.ipynb) for samples.
```
- PluginId: enable_emr_on_eks
  Module: emr_on_eks
  Path: ../plugins/emr_on_eks/
```
#### Parameters 
*None*

References: 
- [Amazon EMR on EKS](https://docs.aws.amazon.com/emr/latest/EMR-on-EKS-DevelopmentGuide/emr-eks.html)

----
### <a name="lustre_plugin">Lustre</a>
This plugin enables Amazon FSx for Lustre file system availabilty to the Orbit platform.  
```
- PluginId: fast_fs_lustre
  Module: lustre
  Path: ../plugins/lustre/
```
#### Parameters 
*None*

References: 
- [Amazon Amazon FSx for Lustre](https://docs.aws.amazon.com/fsx/latest/LustreGuide/what-is.html)

----
### <a name="ray_plugin">Ray</a>
```
- PluginId: ray
  Module: ray
  Path: ../plugins/ray/
  Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
  
```
#### Parameters 

TBD

----

### <a name="sm_operator_plugin">Sagemaker Operator</a>
This plugin enables the kubernetes cluster to execute jobs on Sagemaker from the Orbit platform.  Please see [here](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/notebooks/H-Model-Development/Example-5-SageMaker-on-EKS-xgboost_mnist.ipynb) for samples.
```
- PluginId: sm-operator
  Module: sm-operator
  Path: ../plugins/sm-operator/
```
#### Parameters
*None*

References: 
- [SageMaker Operators for Kubernetes](https://docs.aws.amazon.com/sagemaker/latest/dg/amazon-sagemaker-operators-for-kubernetes.html)
- [SageMaker-Operator-for-K8s Githib repo](https://github.com/aws/amazon-sagemaker-operator-for-k8s)  -  check out the samples too!

----

### <a name="ts_plugin">Team Script Launcher Plugin</a>
```
- PluginId:  
  Module: 
  Path: ../plugins/team_script_launcher/ 
    Parameters:
        script: |
            i=0
            while [ $i -lt 1 ];
            do
              find /efs/shared/regression -mtime +5 -type f -exec rm {} \;
              sleep 60
            done
            echo "DONE LOOP"
        restartPolicy: Never
  
```
#### Parameters 
-*script*

-*restartPolicy*

----
### <a name="op_plugin">Overprovisioning Plugin</a>
This plugin preserve idle capacity on the EKS cluster to allow quick startup time of containers even 
when the cluster has reached its capacity and need to scale up.  Administrator can define how much capacity 
in terms of cpu and memory to preserve for the next containers.  When cluster has utilized all space other than this 
reserve space, it will initiate scale up, but the containers that fits this preserve space can still start immediately. 
```
- PluginId: 
  Module:
  Path: ../plugins/overprovisioning/ 
  Parameters:
    replicas: 3
    cpu: 2
    memory: 4Gi
  
```
#### Parameters 
- *replicas* - number of containers to allocate for the reserve space
- *cpu* - number of cpu for each allocated containers. e.g., '2'
- *memory* - Memory capacity for each container. e.g., '4Gi'

