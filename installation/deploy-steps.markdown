---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: installation
title: Deploy AWS Orbit Workbench
permalink: deploy-steps
---

## Steps to install AWS Orbit Workbench 
This page outlines the steps to deploy an AWS Orbit Workbench.  The workbench source code is found in
the [AWS Labs github repository](https://github.com/awslabs/aws-orbit-workbench/).
<br><br>
Some of these steps (as indicated) will only need to be run once, others can be run multiple times in order to update the deployment.  



### Steps Outline
- Python 3.7 (recommended)
#### Dependancies


<ol>
    <li>Clone <a href="detail-fork">AWS Labs github repository</a> (only once)</li>
    <li>Install the <a href="detail-cli">CLI</a> (only once)</li>
    <li>Install <a href="detail-codeseeder"> AWS Codeseeder</a> (only once)</li>
    <li>Generate a new <a href="detail-manifest"> manifest</a> (only once)</li>
    <li>Deploy a new <a href="detail-foundation"> foundation</a> (only once)</li>
    <li>Deploy a new <a href="detail-toolkit"> toolkit</a> (only once)</li>
    <li>Deploy <a href="detail-credentials"> credentials</a> (only once)</li>
    <li>Deploy <a href="detail-images"> docker images</a> (as needed, infrequently)</li>
    <li>Deploy <a href="detail-environment"> environment</a> (as needed, infrequently)</li>
    <li>Deploy <a href="detail-teams"> teams</a>  (as many times as needed)</li>
</ol>

