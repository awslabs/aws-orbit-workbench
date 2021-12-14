---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Credentials
permalink: detail-credentials
---

# Deploy the AWS Orbit Credentials

This step allows you to deploy credentials used for logging into DockerHub.  
If you are referencing docker images hosted in an account that is not public and
need to be logged in, this is where you do it.
#### Prerequisites
- [CLI](detail-cli) installed
- [CodeSeeder](detail-codeseeder) installed
- [Manifest](detail-manifest) created
- [Toolkit](detail-toolkit) deployed


----
## **Steps to Deploy**
```
orbit deploy credentials -f <manifest.yaml> -u <name> -p <pwd> -r <registry url>
```

```
Options:
  -f, --filename TEXT   The target Orbit Workbench manifest file (yaml).
  -u, --username TEXT   Image Registry username  [required]
  -p, --password TEXT   Image Registry password
  -r, --registry TEXT   Image Registry name/URL
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
```

----
## **Steps to Destroy**
```
orbit destroy credentials -e <env-name> -r -r <registry url>
```


```
Options:
  -e, --env TEXT        Destroy Registry Credentials.  [required]
  -r, --registry TEXT   Image Registry.  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
```