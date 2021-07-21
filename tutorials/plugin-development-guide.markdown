---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Plugin Development Guide
permalink: plugin-development-guide
---


## Plugin Development Guide
 
Orbit Workbench allows extensibility by introducing pluggable CDK resources or executables wrapped under orbit plugins. Each plugin can be a independent python package, installable during run time context. The plugin execution can create CDK resources, return usable commands or python objects to cli, whose inclusion/exclusion depends on ```<team-name>-plugins.yaml``` files at the ```manifest.yaml``` file Plugins attribute level. The plugins are registered with orbit context/team context  by parsing the manifest files.  Adding or removing plugin definitions effectively adds or removes the plugin deployment from the deployed environment.



Plugin hooks and sequence of execution 
    While deploying teams in the Orbit environment, the manifest based plugin declarations are deserialized and iterated to get the hooks mapped to each plugin. Per established mapping between PluginRegistry hooks and plugin hooks, individual hooks are checked for availability in the Orbit CLI code base and respective embedded actions inside the hooks are performed. Example would be installing CDK resources, adding docker image commands, shell script commands etc. 
    
    

Steps for developing sample plugin details 

1) Create orbit plugin python project. Example hello_world has below folder structure. 

    ```hello_world/__init__.py``` holds examples of deploy, destroy, dockerfile_injection and bootstrap_injection hooks usage. 
    ```custom_cfn/__init__.py``` holds examples of pre and post hooks usage.
 
```
plugins
├── hello_world
│    ├── hello_world
│    │   ├── __init__.py # Holds the integration between hooks and actions under the hooks.
│    │   └── hello_cdk.py # Sample helper file holding CDK resources.
│    ├── pyproject.toml
│    ├── requirements-dev.in # Pip requirements file holding references to python modules along with Orbit CLI. 
│    ├── requirements-dev.txt
│    ├── requirements.txt 
│    ├── setup.cfg
│    ├── setup.py
│    ├── MANIFEST.in
│    ├── VERSION
│    ├── fix.sh
│    └── validate.sh
```

2) Add the hook with Orbit CLI PluginRegistries. 
   ```
   # /aws-orbit-workbench/cli/aws_orbit/plugins/hooks.py
   
   def deploy(func: Callable[[str, "Context", "TeamContext", Dict[str, Any]], None]) -> Callable[[str, "Context", "TeamContext", Dict[str, Any]], None]:
    PLUGINS_REGISTRIES.add_hook(hook_name="deploy_hook", func=func)
    return func
   
   ```
 
3) Map plugin functions to plugin registry callable hooks.
   ```
   # /aws-orbit-workbench/plugins/hello_world/hello_world/__init__.py
   
    @hooks.deploy # Hook annotation mapping the plugin function to CLI plugin registry hooks
    def deploy(
        plugin_id: str,
        context: "Context",
        team_context: "TeamContext",
        parameters: Dict[str, Any],
    ) -> None:
        _logger.debug("Running hello_world deploy!")
        sh.run(f"echo 'Team name: {team_context.name} | Plugin ID: {plugin_id}'")
        cdk_deploy(
            stack_name=f"orbit-{context.name}-{team_context.name}-hello",
            app_filename=os.path.join(PLUGIN_ROOT_PATH, "hello_cdk.py"),
            context=context,
            team_context=team_context,
            parameters=parameters,
        )
    # Example for adding Docker image creation plugin hook
    @hooks.dockerfile_injection
    def dockerfile_injection(
        plugin_id: str,
        context: "Context",
        team_context: "TeamContext",
        parameters: Dict[str, Any],
    ) -> List[str]:
        _logger.debug(
            "Team Env: %s | Team: %s | Image: %s",
            context.name,
            team_context.name,
            team_context.image,
        )
        return ["RUN echo 'Hello World!' > /home/jovyan/hello-world-plugin.txt"]
    
    
    @hooks.bootstrap_injection
    def bootstrap_injection(
        plugin_id: str,
        context: "Context",
        team_context: "TeamContext",
        parameters: Dict[str, Any],
    ) -> str:
        _logger.debug("Injecting CodeCommit plugin commands for team %s Bootstrap", team_context.name)
        return """
    #!/usr/bin/env bash
    set -ex
    
    echo 'Hello World 2!' > /home/jovyan/hello-world-plugin-2.txt
    
    """
   
   ```

4) Refer plugin hooks in the CLI code to for consumption. 
 
    Example - Deploy and Destroy hooks
   
   ```   
   # /aws-orbit-workbench/cli/aws_orbit/plugins/__init__.py
   
   def deploy_plugin(self, context: "Context", team_context: "TeamContext", plugin_id: str) -> None:
    self._context = context
    if team_context.name in self._registries:
        if plugin_id not in self._registries[team_context.name]:
            _logger.debug(
                (f"Skipping {plugin_id} deploy for team {team_context.name} because it is not registered.")
            )
            return None
        
        # Referring to required or expected plugin availability, which defines the sequence of the plugin hook execution.
        hook: HOOK_TYPE = self._registries[team_context.name][plugin_id].deploy_hook
        parameters: Dict[str, Any] = self._registries[team_context.name][plugin_id].parameters
        if hook is None:
            _logger.debug(
                (
                    f"Skipping {plugin_id} deploy for team {team_context.name} "
                    "because it does not have deploy hook registered."
                )
            )
            return None
        _logger.debug(f"Deploying {plugin_id} for team {team_context.name}.")
        hook(plugin_id, context, team_context, parameters)
    else:
        _logger.debug(
            "Skipping deploy_plugin for %s/%s because there is no plugins registered.",
            team_context.name,
            plugin_id,
        )
   ```

    Example - dockerfile_injection_hook
    ```
       for plugin in team_context.plugins:
        # Adding plugin modules to image via pip
        plugin_module_name = (plugin.module).replace("_", "-")
        cmds += [f"RUN pip install --upgrade aws-orbit-{plugin_module_name}=={aws_orbit.__version__}"]

        hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
            context=context,
            team_name=team_context.name,
            plugin_name=plugin.plugin_id,
            hook_name="dockerfile_injection_hook",
        )
        if hook is not None:
            plugin_cmds = cast(Optional[List[str]], hook(plugin.plugin_id, context, team_context, plugin.parameters))
            if plugin_cmds is not None:
                cmds += [f"# Commands for {plugin.plugin_id} plugin"] + plugin_cmds
   ```

   Example - bootstrap_injection_hook
   ```
   def _deploy_team_bootstrap(context: "Context", team_context: "TeamContext") -> None:
    for plugin in team_context.plugins:
        hook: plugins.HOOK_TYPE = plugins.PLUGINS_REGISTRIES.get_hook(
            context=context,
            team_name=team_context.name,
            plugin_name=plugin.plugin_id,
            hook_name="bootstrap_injection_hook",
        )
        if hook is not None:
            script_content: Optional[str] = cast(
                Optional[str], hook(plugin.plugin_id, context, team_context, plugin.parameters)
            )
            if script_content is not None:
                client = boto3.client("s3")
                key: str = f"{team_context.bootstrap_s3_prefix}{plugin.plugin_id}.sh"
                _logger.debug(f"Uploading s3://{context.toolkit.s3_bucket}/{key}")
                client.put_object(
                    Body=script_content.encode("utf-8"),
                    Bucket=context.toolkit.s3_bucket,
                    Key=key,
                )
   ```
   
Steps for developing advanced plugins with Helm


1) Create orbit plugin python project. Example ray plugin has below folder structure holding helm chart. 

    ```ray/__init__.py``` holds examples of deploy, destroy hooks usage.
    ```ray/templates/ray-cluster.yaml``` holds examples of yaml template and helper functions.
    
    ```
        ray
        ├── ray
        │    ├── Chart.yaml
        │    ├── __init__.py
        │    ├── templates
        │    │   ├── _helpers.tpl
        │    │   └── ray-cluster.yaml
        │    └── values.yaml
        ├── requirements-dev.in
        ├── requirements-dev.txt
        ├── requirements.txt
        ├── setup.cfg
        ├── setup.py
        ├── pyproject.toml
        ├── MANIFEST.in
        ├── VERSION
        ├── fix.sh
        └── validate.sh
    ```
 
3) Map plugin functions to plugin registry callable hooks. Using orbit helm utils, package the helm repository. Orbit deploy and destory hooks are used to call helm install and uninstall. 
   ```
    # /aws-orbit-workbench/plugins/ray/ray/__init__.py
       
    @hooks.deploy
    def deploy(
        plugin_id: str,
        context: "Context",
        team_context: "TeamContext",
        parameters: Dict[str, Any],
    ) -> None:
        ...    
        repo_location = team_context.team_helm_repository
        repo = team_context.name
        helm.add_repo(repo=repo, repo_location=repo_location)
        chart_name, chart_version, chart_package = helm.package_chart(repo=repo, chart_path=chart_path, values=vars)
        helm.install_chart(
            repo=repo,
            namespace=team_context.name,
            name=f"{team_context.name}-{plugin_id}",
            chart_name=chart_name,
            chart_version=chart_version,
        )
    
    
        @hooks.destroy
        def destroy(
            plugin_id: str,
            context: "Context",
            team_context: "TeamContext",
            parameters: Dict[str, Any],
        ) -> None:
            ...
            helm.uninstall_chart(f"{team_context.name}-{plugin_id}", namespace=team_context.name)

   
   ```
