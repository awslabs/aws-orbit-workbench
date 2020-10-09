# AWS EKS Data Maker

Data & ML Unified Development and Production Environment.

> One-stop-shop solution for data engineers, scientists and analysts powered by AWS

## 1 - Components

DataMaker is built through a composition of several projects with specific scopes, based on different programming languages and sometimes relying on conflicting dependencies. So, in the end, this repository is a [monorepo](https://en.wikipedia.org/wiki/Monorepo) tying up all componets around to deliver a solid and integrated data environment.

| Component | Description | Technologies |
|-----------|-------------|--------------|
| [**CLI**](./cli/) | Controls the whole infrastructure and deploy/destroy all others components | CDK, Kubectl, Eksctl |
| [**JupyterHub**](./images/jupyter-hub/) | JupyterHub application (Server/Hub side)| JupyterHub |
| [**JupyterUser**](images/jupyter-user/) | JupyterHub application (client side) and all Jupyterlab extensions | JupyterLab, React.js |
| [**LandingPage**](images/landing-page/) | DataMaker Landing Page application | React.js |

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
