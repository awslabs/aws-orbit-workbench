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

# Developing locally

## 1 - Requirements

* MacOS *or* Linux
* [git](https://git-scm.com/)
* [python 3.6](https://www.python.org/)
* [node.js](https://nodejs.org/en/)
* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)
* [Docker](https://www.docker.com/)
* [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
* [eksctl](https://docs.aws.amazon.com/eks/latest/userguide/getting-started-eksctl.html)

## 2 - Project Setting Up

### Cloning the code base locally and checkout the k8s branch

* `git clone ssh://git.amazon.com/pkg/DataMakerMain`
* `cd DataMakerMain`
* `git chechout k8s`

### Setting up the local environment

* `./setup.sh`

## 3 - Deploying and Destroying

### Load the python virtual environment

* `source .venv/bin/activate`

### Running static validations

* `./validate.sh`

### Initiating a DataMaker environment with DEMO enabled

* `datamaker init --demo`

### Deploying

* `datamaker deploy`

### Destroying

* `datamaker destroy`

## 4 - Developing with Visual Studio Code [Optional]

### Making vscode available on terminal

* Open vscode GUI
* `View -> Command Palette -> Search for "Shell command: Install 'code' command in Path"`

### Setting up the local environment with vscode extensions and settings

* `./setup-vscode.sh`

### Reopen vscode

* `code .`
