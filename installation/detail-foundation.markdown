---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Foundation
permalink: detail-foundation
---


# Deploy the AWS CodeSeeder toolkit
#### Prerequisites
- [CLI](detail-cli) installed
- [CodeSeeder](detail-codeseeder) installed
- [Manifest](detail-manifest) created

**_IMPORTANT_**
<br>
For the foundation, you may use an existing foundation. You must have defined the following:
- VPC
- Subnets (at least 2 public and 2 private)
- Elastic File System (EFS)
  - the Security Group on the EFS MUST allow all ingress traffic from the VPC CIDR
- Cognito User Pool

If the above is defined, then you can populate the [manifest](orbit-manifest-guide) with these values, removing the need to deploy a separate foundation.

### Steps to Deploy
There are two methods to deploy the foundation:
1. CLI and manifest (preferred method)
2. CLI and parameters (supported)

#### CLI and Manifest
```
orbit deploy foundation -f <manifest.yaml>
```
#### CLI and Parameters
There are parameters that you can pass in without needing a manifest:
```
-n, --name TEXT                 The Name of the Orbit Foundation deployment
  --ssl-cert-arn TEXT             SSL Certificate to integrate the ALB with.
  --custom-domain-name TEXT       The Custom Domain Name to associate the
                                  orbit framework with

  --internet-accessibility / --no-internet-accessibility
                                  Configure for deployment to Private
                                  (internet accessibility) or Isolated (no
                                  internet accessibility) subnets.  [default:
                                  True]

  --max-availability-zones INTEGER
                                  The maximum number of Availability Zones to
                                  attempt to deploy in the VPC  [default: 2]
```                                  


```
orbit deploy foundation -n <name_of_foundation> --custom-domain-name <something> --internet-accessibility --max-availability-zones <int>
```
### Steps to Destroy
```
orbit destroy foundation -n <name_of_foundation>
```
