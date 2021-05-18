---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Working remotely with local workspace
permalink: working-remotely-with-local-workspace
---

## Make sure that your role can assume the team space role you belong to.

Checkout the last step in [Admin Guide](https://github.com/awslabs/aws-orbit-workbench/wiki/Configure-User-Local-Access)

## Install kubectl

```
sudo curl -k -sS -O https://amazon-eks.s3.us-west-2.amazonaws.com/1.19.6/2021-01-05/bin/linux/amd64/kubectl
sudo mv kubectl /usr/local/bin
sudo chmod 755 /usr/local/bin/kubectl
```

## Point your local kubectl to the cluster

Assume the IAM role or user that you were provided with the AWS account access. Then execute the following command to set your Kube context to your cluster:

```
aws eks update-kubeconfig --name orbit-dev-env --role-arn <TEAM_ROLE_ARN> --region <YOUR CLUSTER REGION>
```

The TEAM_ROLE is the role name that you can find in your notebook under the Team Side panel plugin, security category, property 'EksPodRoleArn' , for example : "arn:aws:iam::495869084367:role/orbit-dev-env-lake-user-role"

## Test the connection to your team space

Run ``` kubectl get pods -n <your team name>```. If everything went well, you should be able to see pods running in your orbit namespace

## Sync your file with _kubectl_ or _devspace_

There are two methods you can use to sync your work:

### `kubectl cp`

`kubectl cp` gives you the ability to copy your work to your orbit workspace.

```
kubectl cp <src> <orbit team>/<your container>:<destination path>
```

For example:

```
export DIR = …
kubectl cp $DIR lake-user/jupyter-john:/home/jovyan/private/ --no-preserve=true
```

To get your container:

* Open up your orbit notebook

* ```echo $HOSTNAME```

### ```devspace```

```devspace``` allows you to continuously sync your local and orbit workspace

To install ```devspace```:

https://devspace.cloud/docs/cli/getting-started/installation

To sync:

```
devspace sync --container-path <container path> --local-path <local path> --namespace <your team> --pod <your container>
```

For example:

```
devspace sync --container-path /home/jovyan/private/python-utils --local-path python-utils --namespace lake-creator --pod jupyter-john
```
