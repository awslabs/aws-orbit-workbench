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

* [DockerHub account](https://hub.docker.com/)
* MacOS *or* Linux
* [python 3.6+](https://www.python.org/)
* [node.js](https://nodejs.org/en/)

## 2 - Project Setting Up

### Cloning the code base locally and checkout the k8s branch

* `git clone https://github.com/awslabs/aws-eks-data-maker`
* `cd aws-eks-data-maker`

### Setting up a Python Virtual Environment

* `python -m venv .venv`

### Load the Python Virtual Environment
* `source .venv/bin/activate`

### Setting up the local environment

* `./setup.sh`

## 3 - Deploying and Destroying

### Running static validations

* `./validate.sh`

### Initiating a DataMaker environment with DEMO and DEV enabled

> The `demo` flag will ensure that a mocked environment will also be deployed.
> 
> The `dev` flag will ensure that all artifacts will be built from source (W/o DockerHub and PyPi).

* `datamaker init --demo --dev`

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
