---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: tutorial
title: Plugin Installation
permalink: plugin-installation
---

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
