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

# Developing from Cloud9

## 1 - Prepare the Cloud9 instance

* Stop the instance and increase its EBS to at least 64 GB
* Create a EC2 IAM Role and attach to the EC2 instance
* Start the IDE again and disable the temporary credentials `AWS Cloud9 > Preferences > AWS SETTINGS`

## 1 - Shipping the source code [Necessary only before publicly published]

### Cloning the code base locally and checkout the k8s branch

* `git clone ssh://git.amazon.com/pkg/DataMakerMain`
* `cd DataMakerMain`
* `git chechout k8s`

### Bundling the source code into a ZIP file

* `git archive -o datamaker.zip HEAD`

### Upload it in your Cloud9 environment and unzip

* `File > Upload Local Files... > Select the zip file created above`
* `unzip -o datamaker.zip`

## 2 - Requirements

### [kubectl](https://docs.aws.amazon.com/eks/latest/userguide/getting-started-eksctl.html#eksctl-gs-install-kubectl)

> A command line tool for working with Kubernetes clusters.

* `curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp`
* `chmod +x ./kubectl`
* `sudo mv ./kubectl /usr/local/bin`

### [eksctl](https://docs.aws.amazon.com/eks/latest/userguide/getting-started-eksctl.html)

> A command line tool for working with EKS clusters that automates many individual tasks.

* `curl -o kubectl https://amazon-eks.s3.us-west-2.amazonaws.com/1.17.9/2020-08-04/bin/linux/amd64/kubectl`
* `sudo mv /tmp/eksctl /usr/local/bin`
* `sudo mv ./kubectl /usr/local/bin`

### [Yarn](https://classic.yarnpkg.com/en/docs/install/#centos-stable)

> FAST, RELIABLE, AND SECURE DEPENDENCY MANAGEMENT.

* `curl --silent --location https://dl.yarnpkg.com/rpm/yarn.repo | sudo tee /etc/yum.repos.d/yarn.repo`
* `sudo yum install yarn -y`

## 3 - Deploying

### Setting up the local environment

* `./setup.sh`

### Load the python virtual environment

* `source .venv/bin/activate`

### Running static validations

* `./validate.sh`

### Initiating a DataMaker environment with DEMO enabled

* `datamaker init --demo`

### Deploying

* `datamaker deploy`
* Add your user under the User Pool URL generated in the previous command
* Access the DataMaker URL

### Destroying

* `datamaker destroy`
