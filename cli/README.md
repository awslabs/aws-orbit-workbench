<!--
#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#   
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#   
#        http://www.apache.org/licenses/LICENSE-2.0
#   
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
-->

# AWS Orbit Workbench CLI

## Contributing

## 1 - Requirements

* [DockerHub account](https://hub.docker.com/)
* MacOS *or* Linux
* [python 3.6+](https://www.python.org/)
* [node.js](https://nodejs.org/en/)

## 2 - Project Setting Up

### Cloning the code base locally and enter the CLI component directory

* `git clone https://github.com/awslabs/aws-eks-data-maker`
* `cd aws-eks-data-maker/cli`

### Setting up a Python Virtual Environment

* `python -m venv .venv`

### Load the Python Virtual Environment

* `source .venv/bin/activate`

### Install all packages required for development

* `pip install -r requirements-dev.txt`

## 3 - Deploying and Destroying

### Running static validations

* `./validate.sh`

### Initiating a Orbit Workbench environment with DEMO and DEV enabled

> The `demo` flag will ensure that a mocked environment will also be deployed.
>
> The `dev` flag will ensure that all artifacts will be built from source (W/o DockerHub and PyPi).

* `orbit init --demo --dev`

### Deploying Foundation or Environment

* `orbit deploy foundation -f my-foundation.yaml`
* `orbit deploy env -f my-env.yaml`

### Destroying Foundation or Environment

* `orbit destroy foundation --name my-foundation`
* `orbit destroy env --env my-env`

## 4 - Assuming Admin Role to Access EKS

* Install [kubectl](https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html)
* Go to the IAM console
* Find the Admin Role (`arn:aws:iam::{ACCOUNT_ID}:role/orbit-{ENV_NAME}-{REGION}-admin`).
* Add your user or role under the `Trust Relationship` tab.

```json
{
    "Effect": "Allow",
    "Principal": {
        "AWS": "arn:aws:iam::{ACCOUNT_ID}:user/{USERNAME}"
    },
    "Action": "sts:AssumeRole"
},
```

* Open the temrinal and user the AWS CLI to configure your kubeconfig
* `aws eks update-kubeconfig --name orbit-{ENV_NAME} --role-arn arn:aws:iam::{ACCOUNT_ID}:role/orbit-{ENV_NAME}-{REGION}-admin`
* Validate you access
* `kubectl get pod -A`

## 5 - Visual Studio Code tips

### Recommended extensions

* [ms-python.python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
* [kddejong.vscode-cfn-lint](https://marketplace.visualstudio.com/items?itemName=kddejong.vscode-cfn-lint)

### Recommended settings

```json
{
    "cfnLint.ignoreRules": [
        "E1029",
        "E3031"
    ],
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.linting.pylintEnabled": false
}
```
