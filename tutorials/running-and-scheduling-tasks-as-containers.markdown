---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: default
title: Running and Scheduling Tasks as Containers
permalink: running-and-scheduling-tasks-as-containers
---
{% include navigation.html %}
# {{ page.title }}
## Running and scheduling containers

Orbit provides multiple ways of running and scheduling containers.

Currently, two types of tasks are supported: a) Jupyter Notebooks b). Python Module

You can run tasks using the 1) CLI Command 2) Orbit SDK API Call 3) Jupyter Cell Magic.  

1. The following example runs a notebook using Orbit CLI

```shell
cat <<EOF |  orbit run notebook --env dev-env --team my-team --user john-doe --wait --tail-logs -
{
      "compute": {
          "container" : {
              "p_concurrent": "1"
          },
          "node_type": "ec2"
      },
      "tasks":  [
            {
                  "notebookName": "Example-1-SQL-Analysis-Athena.ipynb",  # The notebook name to run
                  "sourcePath": "shared/samples/notebooks/B-DataAnalyst", # The EFS folder in shared where the notebook resides
                  "targetPath": "shared/regression/notebooks/B-DataAnalyst", # The EFS target location where the folder should be written
                  "targetPrefix": "ttt", # Any prefix to append to the name of the output nodebook
                  "params": {  # Parameters map to replace the variables' values define in the cell tag with 'parameters'
                        "glue_db" : "cms_raw_db",
                        "target_db" : "users"
                  }      
            }
      ]  
 }
EOF
```

2.  The following example runs a notebook using Orbit SDK Call:

```python
notebooksToRun = {
      "compute": {
          "container" : {
              "p_concurrent": "1" # how many threads will run on the container to execucte tasks
          },
          "node_type": "ec2", # fargate is an option if it is enabled by your orbit team deployment
          "profile": "nano" # You can define the profile to be used for the container.  
                            # The profile define your compute requirements as well as the image the container use.
                            # See more examples in I-Image folder
      },
      "tasks":  [
            {
                  "notebookName": "Example-1-SQL-Analysis-Athena.ipynb",  # The notebook name to run
                  "sourcePath": "shared/samples/notebooks/B-DataAnalyst", # The EFS folder in shared where the notebook resides
                  "targetPath": "shared/regression/notebooks/B-DataAnalyst", # The EFS target location where the folder should be written
                  "targetPrefix": "ttt", # Any prefix to append to the name of the output nodebook
                  "params": {  # Parameters map to replace the variables' values define in the cell tag with 'parameters'
                        "glue_db" : "cms_raw_db",
                        "target_db" : "users"
                  }      
            }
      ]  
}
containers = controller.run_notebooks(notebooksToRun) # Starts a single container to execute give task
```

The return value will be of this structure, where the 'Identifier' holds the Kubernetes Job ID.
```json
{"ExecutionType": "eks",
 "Identifier": "orbit-lake-user-ec2-runner-grzdr",
 "NodeType": "ec2",
 "tasks": [{"notebookName": "Example-1-SQL-Analysis-Athena.ipynb",
   "sourcePath": "shared/samples/notebooks/B-DataAnalyst",
   "targetPath": "shared/regression/notebooks/B-DataAnalyst",
   "targetPrefix": "ttt",
   "params": {"glue_db": "cms_raw_db", "target_db": "users"}}]}
```

3. Running and Scheduling using Jupyter Magic

```jupyter
%%run_notebook
{    
      "tasks":  [
            {
                  "notebookName": "Example-1-SQL-Analysis-Athena.ipynb",
                  "sourcePath": "shared/samples/notebooks/B-DataAnalyst",
                  "targetPath": "shared/regression/notebooks/B-DataAnalyst",
                  "targetPrefix": "ttt",
                  "params": {
                        "glue_db" : "cms_raw_db",
                        "target_db" : "users"
                  }      
            }
      ]  
}
```


### More Examples:
-  [Running and Scheduling Notebooks](https://nbviewer.jupyter.org/github/awslabs/aws-orbit-workbench/blob/main/samples/notebooks/B-DataAnalyst/Example-8-SDK-Controller-Sched.ipynb)
-  [Running and Scheduling Python](tbd)
-  [Parallel Programming using Orbit SDK](tbd)
