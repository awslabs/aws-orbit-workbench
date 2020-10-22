# AWS EKS Data Maker

Data & ML Unified Development and Production Environment.

> One-stop-shop solution for data engineers, scientists and analysts powered by AWS

[![Python Version](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-brightgreen.svg)](https://github.com/awslabs/aws-eks-data-maker)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
![Static Checking](https://github.com/awslabs/aws-eks-data-maker/workflows/Static%20Checking/badge.svg?branch=main)

## 1 - Components

DataMaker is built through a composition of several components with specific scopes, based on different programming languages and sometimes relying on conflicting dependencies. So, in the end, this repository is a [monorepo](https://en.wikipedia.org/wiki/Monorepo) tying up all components around to deliver a solid and integrated data environment.

| Component | Description | Technologies |
|-----------|-------------|--------------|
| [**CLI**](cli/) | Deploy/destroy the infrastructure and all others components | CDK, Kubectl, Eksctl |
| [**JupyterHub**](images/jupyter-hub/) | JupyterHub application (Server/Hub side)| JupyterHub |
| [**JupyterUser**](images/jupyter-user/) | JupyterHub application (client side) and all Jupyterlab extensions | JupyterLab, React.js |
| [**LandingPage**](images/landing-page/) | DataMaker Landing Page application | React.js |
| [**SDK**](sdk/) | Python package to interact with DataMaker programmatically | Python3 |

## 2 - Contributing

Contributing Guidelines: [./CONTRIBUTING.md](././CONTRIBUTING.md)

Also, check our development guides under [docs/contributing](./docs/contributing/).

## 3 - License

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.         
                                                                           
  Licensed under the Apache License, Version 2.0 (the "License").          
  You may not use this file except in compliance with the License.         
  You may obtain a copy of the License at                                  
                                                                        
      http://www.apache.org/licenses/LICENSE-2.0                           
                                                                           
  Unless required by applicable law or agreed to in writing, software      
  distributed under the License is distributed on an "AS IS" BASIS,        
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
  See the License for the specific language governing permissions and      
  limitations under the License.                                           
