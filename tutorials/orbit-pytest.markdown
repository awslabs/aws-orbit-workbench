---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Orbit PyTest
permalink: orbit-pytest
---

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

## Useful Links

* [PyTest](https://docs.pytest.org)
* [Kubetest](https://kubetest.readthedocs.io/en/latest/)

## Environment variables

* AWS_ORBIT_ENV - Set to Orbit Environment name
* AWS_ORBIT_TEAM_SPACE - Set to Orbit Teamspace



## PyTest scripts

* /aws-orbit-workbench/test/regressions/scripts
  ├── pytest-lake-admin.sh
  ├── pytest-lake-creator.sh
  └── pytest-lake-user.sh


## Triggering PyTests
* Orbit PyTest interanlly use KubeTest Python module to interact with EKS cluster. 
* Orbit extends KubeTest [ApiObject](https://kubetest.readthedocs.io/en/latest/_modules/kubetest/objects/api_object.html) to allow interaction with Orbit defined Kubernetes Custom Resource Defination(s) and Custom Resource(s). 
* Orbit PyTests will create, fetch status and delete the Orbit Custom Resources.
* Orbit Controller image running the individual Custom Resource operators will act upon the Custom Resource object events and updates the relavent processing status to the Custom Resource object.
* PyTest will utilize the Custom Resource status values to assert the testing outcome.
