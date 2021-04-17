---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: default
title: Prepare User Local Access
permalink: prepare-user-local-access
---
{% include navigation.html %}
# {{ page.title }}

Orbit Environment Administrators should follow these steps to allow users to access their namespace from their local development machines.

## Grant AssumeRole to your Team IAM role

1. Go to your IAM console -> Roles

2. Search for the team role.  The team role is the role name that you can find in the team's notebook under the Team Side panel plugin, security category, property 'EksPodRoleArn' , for example : "arn:aws:iam::495869084367:role/orbit-dev-env-lake-user-role"

3. Trust relationships -> Edit trust relationship

4. Add the users' IAM role/user to the trust relationship. Example:

   ```json
   {
         "Effect": "Allow",
         "Principal": {
           "AWS": "<YOUR_ROLE_ARN>"
         },
         "Action": "sts:AssumeRole"
   },
   ```

## Create a role policy for the users
Sample policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "eks:DescribeCluster",
            "Resource": "<Your Orbit EKS Cluster ARN>"
        }
    ]
}
```
The Orbit EKS Cluster ARN can be found in the EKS Console under configuration tab / Details : Cluster ARN.
