---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: tutorial
title: Administrative Teams
permalink: administrative-teams
---
### Purpose

- A single place for environment administrators to log-in and perform administrative actions
- Perform envionment actions such as
  - Remove and add node pools
  - Create and delete persistent volumes
  - Manage other team namespaces resources
  - Deploy additional Kubernetes applications
  - Perform orbit deploy\destroy commands to add\remove teams or update environment

### Description
During team deployment, a team can be designated as administration team by setting the K8Admin to True in the Team manifest.  This will turn bind the team to the Kubernetes cluster admin role and will allow team members to execute any actions on all cluster name spaces and to perform cluster administration. The team is bounded to the IAM policies that are attached to it by the manifest 'Policies' property. Therefore, to allow administrative actions in the AWS resources, an IAM policy with the allowed actions much be also attached to the team.

```yaml
-   Name: admin-team
    Policies:
    - orbit-admin-policy  # A custom admin policy to allow actions on Orbit resources in the AWS cloud
    GrantSudo: true. # Ability for users to perform sudo actions on their notebooks and containers
    K8Admin: true # Upgrade the user Kubernetes permissions to K8 cluster admin
```
