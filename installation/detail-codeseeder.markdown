---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: AWS Codeseeder
permalink: detail-codeseeder
---

# Deploy the AWS CodeSeeder toolkit
#### Prerequisites
- [CLI](detail-cli) installed
- VirtualEnv (.venv) is active and the same that has AWS Orbit installed
<br>

**_IMPORTANT_**<br>
You only need ONE Seedkit per AWS Region for ALL Orbit Workbench deployments<br>

----
## **Steps**
1. Install the AWS CodeSeeder python library
```
pip install aws-codeseeder
``` 
2. Create a Seedkit for orbit  
```
codeseeder deploy seedkit orbit
```