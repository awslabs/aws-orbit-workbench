---
layout: documentation
title: Documentation
permalink: /documentation
---

# What is AWS Orbit Workbench?

AWS Orbit Workbench is a framework for building data platforms on AWS.  You can build a data platform that gives you access to 
the right tools for your use cases, either through the out-of-the-box in [integrations](/aws-orbit-workbench/#integrations)
or through the extensible architecture.  You also have control over the underlying infrastructure, whether your work
needs extra GPUs, extra memory or could save money by running on the newest [Graviton2](https://aws.amazon.com/ec2/graviton/) processors. 
AWS Orbit Workbench is built on Kubernetes, making it easy to deploy, scale and 
rapidly iterate.

This introduction to AWS Orbit Workbench provides a detailed summary.  After reading this section, you should have a good 
idea of what it offers and how it can fit into your business.

## Advantages of using AWS Orbit Workbench

AWS Orbit Workbench has been built to let you build a secure data platform on AWS and give you control over the services you use,
and the infrastructure you run on.  Advantages of using AWS Orbit Workbench are:

* **Work efficiently** - Use analytical and machine learning services from AWS and partners to efficiently
  work on data-driven projects.
* **Securely collaborate** - You can collaborate with your team, exchanging data and code, but you are prevented from sharing
* **Quickly move to production** - Scale instantly by running your workloads on a Kubernetes cluster.
* **Easily extend** - Add extra integrations to any service through the pluggable architecture.

## AWS Orbit Workbench concepts

This section describes the key concepts and terminology you need to understand to use AWS Orbit Workbench effectively.

### Topics
#### Environment
#### Team Space
AWS Orbit Workbench creates a team space for each team.  A team space consists of:
* Storage:
  - A shared drive on Amazon EFS that the team can use as block storage
  - An area on Amazon S3 for object storage
* A pool of compute (CPU and GPU) resource in a Kubernetes cluster that the team can use to run apps.

#### Apps
Teams can launch Apps on containers in their Kubernetes cluster.  An App could provide an integrated development environment
(IDE) such as Jupyter or Visual Code.  It could also provide a service, for example Voila can turn a Jupyter notebook into a 
stand alone web application, so you can easily share your work with the rest of your organisation.
#### Integrations
#### Orchestrations




### Contributing

Contributing Guidelines: [./CONTRIBUTING.md](././CONTRIBUTING.md)


### License

This project is licensed under the Apache-2.0 License.

<a name="myfootnote1">**</a>: for detailed feature list by release, please see our release page in the wiki tab
