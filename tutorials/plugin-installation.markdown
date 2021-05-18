---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Plugin Installation
permalink: plugin-installation
---

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

### <a name="rs_plugin">Amazon Redshift </a>
```
- PluginId: 
  Module: 
  Path: ../plugins/redshift/
  Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
  
```
#### Parameters 
### <a name="codecommit_plugin">AWS Code Commit </a>
```
- PluginId: code_commit
  Module: code_commit
  Path: ../plugins/code_commit/ 
```
#### Parameters 
None
### <a name="cfn_plugin">AWS Cloudformation </a>
```
- PluginId: 
  Module: 
  Path: ../plugins/custom_cfn/
  Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
  
```
#### Parameters 
### <a name="emreks_plugin">EMR on EKS </a>
```
- PluginId: enable_emr_on_eks
  Module: emr_on_eks
  Path: ../plugins/emr_on_eks/
```
#### Parameters 
None
### <a name="lustre_plugin">Lustre</a>
```
- PluginId: fast_fs_lustre
  Module: lustre
  Path: ../plugins/lustre/
```
#### Parameters 
None
### <a name="ray_plugin">Ray</a>
```
- PluginId: 
  Module: 
  Path: ../plugins/ray/
  Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
  
```
#### Parameters 
### <a name="sm_operator_plugin">Sagemaker Operator</a>
```
- PluginId: sm-operator
  Module: sm-operator
  Path: ../plugins/sm-operator/
```
#### Parameters
None 
### <a name="ts_plugin">Team Script Launcher Plugin</a>
```
- PluginId:  
  Module: 
  Path: ../plugins/team_script_launcher/ 
    Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
  
```
#### Parameters 
### <a name="op_plugin">Overprovisioning Plugin</a>
```
- PluginId: 
  Module:
  Path: ../plugins/overprovisioning/ 
    Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
  
```
#### Parameters 




