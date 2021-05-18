---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Plugin Installation
permalink: plugin-installation
---

Orbit plugins are individual python modules published PyPi.  We are continually adding plugin capabilites to the platform.  This is the current list of published plugins:
 - [Hello World Plugin](#hw_plugin)
 - [Amazon Redshift Plugin](#rs_plugin)
 - [AWS Code Commit Plugin](#codecommit_plugin)
 - [Custom AWS Cloudformation Plugin](#cfn_plugin)
 - [EMR on EKS Plugin](#emreks_plugin)
 - [Lustre Plugin](#lustre_plugin)
 - [Ray Plugin](#ray_plugin)
 - [SageMaker-Operators for K8s Plugin](#sm_operator_plugin)
 - [Team Script Plugin](#ts_plugin)
 - [Overprovisioning Plugin](#op_plugin)

Each Plugin has a configuration that you need to define.  The structure is as follows (in yaml format):

```
- PluginId: <the name of the plugin>
  Module: <the module name>
  Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
```

### <a name="hw_plugin">Hello World </a>
This is the standard 'is everything ok' example of how to configure plugins.
```
- PluginId: hello_world
  Module: hello_world
    Parameters:
    - parameter 1: <value>
    - parameter 2: <value>
    ...
    - parameter N: <value>
  
```
#### Parameters    
### <a name="rs_plugin">Amazon Redshift </a>
### <a name="codecommit_plugin">AWS Code Commit </a>
### <a name="cfn_plugin">AWS Cloudformation </a>
### <a name="emreks_plugin">EMR on EKS </a>
### <a name="lustre_plugin">Lustre</a>
### <a name="ray_plugin">Ray</a>
### <a name="sm_operator_plugin">Sagemaker Operator</a>
### <a name="ts_plugin">Team Script Plugin</a>
### <a name="op_plugin">Overprovisioning Plugin</a>



Orbit plugins are individual python modules published PyPi. Use `pip install <plugin_module_name>` to install in a specific python environment.

List of plugins and respective pip install command.

* Amazon Redshift
> `pip install aws-orbit-redshift`
* Team Pod launcher
> `pip install aws-orbit-team-script-launcher`
* Amazon CodeCommit
> `pip install aws-orbit-code-commit`
* Custom CloudFormation template runner
> `pip install aws-orbit-custom-cfn`
* Hello World
> `pip install aws-orbit-hello-world`



Using plugin files (example - [lake-creator plugin](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/manifests/demo/lake-creator-plugins.yaml) declare the plugin requirement for a team (example [lake-creator team](https://github.com/awslabs/aws-orbit-workbench/blob/main/samples/manifests/demo/manifest.yaml#L41)). The declaration includes PluginId, plugin module name, path of plugin code and optional parameters.
