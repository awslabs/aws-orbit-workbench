[![Python Version](https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8-brightgreen.svg)](https://github.com/awslabs/aws-eks-data-maker)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
![Static Checking](https://github.com/awslabs/aws-eks-data-maker/workflows/Static%20Checking/badge.svg?branch=main)


<a href="url"><img src="https://github.com/awslabs/aws-orbit-workbench/blob/main/images/landing-page/src/images/orbit1.jpg?raw=true" align="right" height="30%" width="30%" style="float:right"></a>

Orbit Workbench is an open framework for building team-based secured data environment. Orbit workbench is built on Kubernetes using Amazon Managed Kubernetes Service (EKS), and provides both a command line tool for rapid deployment as well as Python SDK, Jupyter Plugins and more to accelerate data analysis and ML by integration with AWS analytics services such as Amazon Redshift, Amazon Athena, Amazon EMR, Amazon SageMaker and more. 

Orbit Workbench deploys secured team spaces that are mapped to Kubernetes namespaces and span into AWS cloud resources.  Each team is a secured zone where only members of the team can access allowed data and share data and code freely within the team.  Orbit automatically creates file storage for each team using Amazon EFS,  security group and IAM role for each team , as well as their own JupyterHub and Jupyter Server.  Orbit workbench users are also capable of launching python code or Jupyter Notebooks as Kubernetes containers or as Amazon Fargate containers. Orbit workbench provides CLI tool for users to build their own custom images and use it to deploy containers or customize their Jupyter environment.

GPU-based algorithms are easily supported by Orbit that pre-configures EKS to allow GPU loads as well as provide examples of how to build images that support GPU accelerations.

If you are looking to build your own Data & ML Platform for your company on AWS, give Orbit Workbench a chance to accelarate your business outcome using AWS Services.


Contributors are welcome!

Please see our [./Home.md](././Home.md) for installation and usage guides.

##  Feature List 
(for detailed feature list by release, please see our release page in the wiki tab)

- Collaborative Team Spaces
  - Isolated Team spaces with pre-provisioned access to data sources
  - Team isolation enforced by EKS Namespace as well as AWS constructs such as security groups and roles
  - Shared file system between team users via EFS
  - Scratch shared space for your team only on S3 with defined expiration time 
  - Jupyter Plugin to support users with Kubernetes (Jobs, Pods, Volumes and more ) 
    and AWS resources (Athena, Redshift, Glue Catalog, S3, and more)

- Compute
  - Build your own docker image using Orbit CLI on a remote AWS codebuild and into ECR Repository
  - Support for GPU Node pools 
  - Support Dockers with GPU drivers for use of PyTorch, TensorFlow, and others
  - Shared node pools for all teams with storage isolation
  - Auto-Scaling EKS Node pools (coming soon)
    
- Security
  - Jupyter Hub integration with SSO Providers via Cognito
  - Ability to map SSO Group to a team to control authentication     

- Deployment
  - Deployment of all AWS and EKS resources via a simple declarative manifest
  - Ability to add and remove teams dynamically 
  - Support for Kubernetes Administrative Teams 

- AWS Analytic Services Integrations
  - Amazon Redshift
  - Amazon SageMaker (api calls)
  - Amazon EMR (coming soon)
  - Amazon Athena
  - AWS Glue 
  - AWS Lake Formation (coming soon)
    
## Contributing

Contributing Guidelines: [./CONTRIBUTING.md](././CONTRIBUTING.md)


## License

This project is licensed under the Apache-2.0 License.
