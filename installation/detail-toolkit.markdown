---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Toolkit
permalink: detail-toolkit
---

# Deploy the AWS Orbit Toolkit

This step will deploy the Oribe Env Toolkit that supports the workbench for deployment artifacts.
#### Prerequisites
- [CLI](detail-cli) installed
- [CodeSeeder](detail-codeseeder) installed
- [Manifest](detail-manifest) created
- [Foundation](detail-foundation) deployed


----
## **Steps to Deploy**
```
orbit deploy toolkit -f <manifest.yaml>
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
orbit destroy toolkit -e <env-name>
```
```
Options:
  -e, --env TEXT        Environment name is required  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
```  