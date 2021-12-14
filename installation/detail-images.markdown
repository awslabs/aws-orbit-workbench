---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Images
permalink: detail-images
---

This step will compile and deploy the docker images required to support the workbench.
The images provided are:
- k8s-utilities (the base for the following images)
- orbit-controller (an image with the k8s Operators for Orbit)
- jupyter-user (the notebook image)
- utility-data (the regression data and sample notebooks)

# Deploy the AWS Orbit Images
#### Prerequisites
- [CLI](detail-cli) installed
- [CodeSeeder](detail-codeseeder) installed
- [Manifest](detail-manifest) created


----
## **Steps to Deploy**
The first time you deploy a new Orbit Environment, the following command **MUST** be run
```
orbit deploy images -f <manifest.yaml>
```
On subsequent runs, you can build one of the images directly by passing in the case-sensitve name of the image to rebuild it.
```
orbit deploy images -f <manifest.yaml> -i jupyter-user
```

```
Options:
  -f, --filename TEXT   The target Orbit Workbench manifest file (yaml).
                        [required]

  -i, --image TEXT      The name of ONE image to build- MUST match dir in
                        'images/', else ALL built

  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
```

----
## **Steps to Destroy**
```
orbit destroy images -e <env-name>
```
```
Options:
  -e, --env TEXT        Environment name is required  [required]
  --debug / --no-debug  Enable detailed logging.  [default: False]
  --help                Show this message and exit.
```