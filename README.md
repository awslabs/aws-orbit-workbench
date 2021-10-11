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

Please see our [Home](https://awslabs.github.io/aws-orbit-workbench) for installation and usage guides.

##  Feature List <sup>[**](#myfootnote1)</sup>

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
  - Amazon SageMaker api calls and Kubernetes Operator
  - Amazon EMR on EKS Kubernetes Operator
  - Amazon Athena
  - AWS Glue DataBrew
  - AWS Lake Formation
    

## Create an AWS Orbit Workbench trial environment

Feel free to create a full AWS Orbit Workbench environment in its own VPC.  
You can always clone or fork this repo and install via CLI, but if you are just investigating the Workbench,
we have provided a standard deployment. 

Please follow these steps.
#### 1. Create the AWS Orbit Workbench

Deploy | Region Name | Region  
:---: | ------------ | -------------  
[🚀][us-east-1] | US East (N. Virginia) | us-east-1  
[🚀][us-east-2] | US East (Ohio) | us-east-2  
[🚀][us-west-1] | US West (N. California) | us-west-1  
[🚀][us-west-2] | US West (Oregon) | us-west-2  
[🚀][eu-west-2] | EU (London) | eu-west-2  


This reference deployment can only be deployed to Regions denoted above.

The CloudFormation template has all the necessary parameters, but you may change as needed:

- Cloudformation Parameters
  - **Version**: The version of Orbit Workbench (corresponds to the versions of
                [aws-orbit](https://pypi.org/project/aws-orbit/]aws-orbit) in pypi)
  - **K8AdminRole**: An existing role in your account that has admin access to the EKS cluster


- The Cloudformation stack will create two(2) [AWS CodePipelines](https://aws.amazon.com/codepipeline/):
  - **Orbit_Deploy_trial** - which will start automatically and create your  workbench
  - **Orbit_Destroy_trial** - which will start automatically and will destroy your workbench
    - this pipeline has a Manual Approval stage that prevents your workbench from moving forward with 
      the destroy process  

Once your pipelines are created, the **Orbit_Destroy_trial** pipeline will wait for you to approve the next stage (which we don't want to do yet).

Go to the **Orbit_Destroy_trial** pipeline, click `Stop Execution` then `Stop and Abandon`. Abandoning the
pipeline prevents the job from timing out and stopping at a later time.

The **Orbit_Deploy_trial** pipeline takes approximaeluy `70-90 minutes` to complete.

#### 2. Get your access URL

When the Orbit_Deploy_trial pipeline does complete, go to the EC2 page --> Load Balancing --> Load Balancers and 
look for the alb we have created...it have a naming pattern of `xxxxxxxx-istiosystem-istio-xxxx`.  Get the DNS of the alb.

The AWS Orbit Workbench homepage will be located at:
```console
https://xxxxxxxx-istiosystem-istio-xxxx-1234567890.{region}.elb.amazonaws.com/orbit/login
```

You can browse that url.  We are using self-signed certs, so your browser may complain, 
but it is save to `Accept and Continue` to the site.

The default username and password are:
```console
Username: orbit
Password: OrbitPwd1!
```
You will be promted to change the password.


### Cleaning up the example resources

To remove all workbench resources , do the following:

1. Goto the **Orbit_Destroy_trial** pipeline and click 'Release Change'
   - When the `CLI_ApproveDestroy` stage is active, click `Review` and then `Approve` so the pipeline will continue
2. Wait until the **Orbit_Destroy_trial** completes 
3. Delete the Cloudformation Stack `trial`
   - if the template fails to destroy due to objects in the S3 bucket, it is ok to 
     `Empty` the bucket and delete the stack again


## Contributing

Contributing Guidelines: [./CONTRIBUTING.md](././CONTRIBUTING.md)


## License

This project is licensed under the Apache-2.0 License.

<a name="myfootnote1">**</a>: for detailed feature list by release, please see our release page in the wiki tab


[us-east-1]: https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?region=us-east-1&templateURL=https://aws-orbit-workbench-public-us-east-1.s3.amazonaws.com/deploy/trial_pipeline_cfn.yaml&stackName=trial

[us-east-2]: https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?region=us-east-2&templateURL=https://aws-orbit-workbench-public-us-east-2.s3.amazonaws.com/deploy/trial_pipeline_cfn.yaml&stackName=trial

[us-west-1]: https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?region=us-west-1&templateURL=https://aws-orbit-workbench-public-us-west-1.s3.amazonaws.com/deploy/trial_pipeline_cfn.yaml&stackName=trial

[us-west-2]: https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?region=us-west-2&templateURL=https://aws-orbit-workbench-public-us-west-2.s3.amazonaws.com/deploy/trial_pipeline_cfn.yaml&stackName=trial

[eu-west-2]: https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?region=eu-west-2&templateURL=https://aws-orbit-workbench-public-eu-west-2.s3.amazonaws.com/deploy/trial_pipeline_cfn.yaml&stackName=trial
