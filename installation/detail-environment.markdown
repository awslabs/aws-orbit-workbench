---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Environment
permalink: detail-environment
---

Once you have the prerequsites met, you can deploy the Orbit Workbench environment.
This will deploy the k8s cluster and the compute nodes, and install the applications that comprise the workbench.

<br><br>
This can be run multiple times.  It takes approximately 50 minutes for the first deployment.
# Deploy the AWS Orbit Environment
#### Prerequisites
- [CLI](detail-cli) installed
- [CodeSeeder](detail-codeseeder) installed
- [Manifest](detail-manifest) created
- [Foundation](detail-foundation) deployed
- [Toolkit](detail-toolkit) deployed
- [Credentials](detail-credentials) deployed (optional)
- [Images](detail-images) deployed

----
## **Steps to Deploy**
```
orbit deploy env -f <manifest.yaml>
```
```
Options:
  -f, --filename TEXT   The target Orbit Workbench manifest file (yaml).
                        [required]

  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
```

----
## **Steps to Destroy**
```
orbit destroy env -e <env-name>
```
```
Options:
  -e, --env TEXT                  Destroy Orbit Environment.  [required]
  --preserve-credentials / --destroy-credentials
                                  Preserve any docker credentials in Secrets
                                  Manager.  [default: True]

  --debug / --no-debug            Enable detailed logging.  [default: False]
  --help                          Show this message and exit.
``` 