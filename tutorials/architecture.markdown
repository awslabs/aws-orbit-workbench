---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: default
title: Architecture
permalink: architecture
---
{% include navigation.html %}
# {{ page.title }}

## High Level Architecture

![Architecture](https://raw.githubusercontent.com/wiki/awslabs/aws-orbit-workbench/Orbit-WorkBench-Arch.svg)

## Components

Orbit Workbench is built through a composition of several components with specific scopes, based on different programming languages and sometimes relying on conflicting dependencies. So, in the end, this repository is a [monorepo](https://en.wikipedia.org/wiki/Monorepo) tying up all components around to deliver a solid and integrated data environment.

| Component | Description | Technologies |
|-----------|-------------|--------------|
| [**CLI**](https://github.com/awslabs/aws-orbit-workbench/blob/main/cli/) | Deploy/destroy the infrastructure and all others components | CDK, Kubectl, Eksctl |
| [**JupyterHub**](https://github.com/awslabs/aws-orbit-workbench/blob/main/images/jupyter-hub/) | JupyterHub application (Server/Hub side)| JupyterHub |
| [**JupyterUser**](https://github.com/awslabs/aws-orbit-workbench/blob/main/images/jupyter-user/) | JupyterHub application (client side) and all Jupyterlab extensions | JupyterLab, React.js |
| [**LandingPage**](https://github.com/awslabs/aws-orbit-workbench/blob/main/images/landing-page/) | Orbit Workbench Landing Page application | React.js |
| [**SDK**](sdk/) | Python package to interact with Orbit Workbench programmatically | Python3 |
