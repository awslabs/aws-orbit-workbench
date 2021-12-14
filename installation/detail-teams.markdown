---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Teams
permalink: detail-teams
---
This step deploys the teams associated with the workbench.

It can be deployed multiple times to support:
- addition / removal of teams
- deplpoyment / destruction of [plugins](plugin-library) per team
# Deploy the AWS Orbit Teams
#### Prerequisites
- [CLI](detail-cli) installed
- [CodeSeeder](detail-codeseeder) installed
- [Manifest](detail-manifest) created
- [Foundation](detail-foundation) deployed
- [Toolkit](detail-toolkit) deployed
- [Credentials](detail-credentials) deployed (optional)
- [Images](detail-images) deployed
- [Environment](detail-environment) deployed

----
## **Steps to Deploy**
```
orbit deploy teams -f <manifest.yaml>
```
```
Options:
  -f, --filename TEXT   The target Orbit Workbench manifest file (yaml).
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
```

----
## **Steps to Destroy**
```
orbit destroy teams -e <env-name>
```
```
Options:
  -e, --env TEXT        Destroy Orbit Teams.  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
``` 