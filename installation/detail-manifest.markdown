---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Manifest
permalink: detail-manifest
---


# Generate Orbit Manifest

This document refers to creating a [manifest](orbit-manifest-guide) for your workbench.  
#### Prerequisites
- [CLI](detail-cli) installed
- [AWS CodeSeeder](detail-codeseeder) installed

----

## **Steps**

```
orbit init -n <env-name> -r <region>
```


```
Options:
  -n, --name TEXT       The name of the Orbit Workbench enviroment. MUST be
                        unique per AWS region.  [default: my-env]

  -r, --region TEXT     AWS Region name (e.g. us-east-1). If None, it will be
                        infered.

  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
```