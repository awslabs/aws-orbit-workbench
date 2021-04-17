---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: default
title: Deploying From Source
permalink: deploying-from-source
---
{% include navigation.html %}
# {{ page.title }}
## First an explanation on the how and why:

The CLI is intended to be light weight with very few dependencies. In addition, some deploy/destroy operations are long running (EKS Clusters, EKS NodeGroups, etc). Interruption of a deploy/destroy operation can leave the environment in an unstable state. To help avoid this, the operation needs to survive CLI interruptions.

The CLI first deploys a small CloudFormation stack that includes: the Orbit Admin Role, a CodeBuild Project, S3 Bucket to store artifacts, and a KMS Key to encrypt artifacts. The CLI then uses the CodeBuild Project as a remote executor; handing off and monitoring the deploy/destroy operations. If the CLI is interrupted, the CodeBuild Project will continue executing.

In order to deploy the environment from source control, a CodeArtifact Repository is utilized to store the CLI and SDK packages. During deployment these libraries are installed from this repository when the CodeBuild Project initializes and when the Docker images are built. As changes are made to the CLI or SDK these packages need to be pushed to the CodeArtifact Repository before executing the destroy/deploy operation.

Scripts are provided to simplify initialization of the CodeArtifact Repository, building and pushing packages to the repository, and enable login to the CodeArtifact Repository during Docker image builds.


## Deploying from Source
_As a prerequisite, you will need AWS Account credentials configured for the AWS CLI commands used in the scripts below._

1. Clone the GitHub repo
   ```
   git clone https://github.com/awslabs/aws-orbit-workbench
   cd aws-orbit-workbench
   ```

2. Create and activate a Python virtual environment for the CLI
   ```
   cd cli/
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Prep the Development CodeArtifact Repo
   ```
   ../scripts/init_codeartifact.sh
   ```

4. Install the AWS Orbit Workbench
   ```
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

5. Prep the AWS Account
   ```
   ../scripts/prep_build_from_source.sh --all
   ```

   **Note: You can also pass `--cli`, `--sdk`, or `--plugins` to update the packages of that module in CodeArtifact, or `--all` for all modules**


6. Deploy the Orbit Foundation Stacks

   _The username/password here are for Dockerhub to avoid throttles_
   ```
   orbit deploy foundation -n dev-env --codeartifact-domain aws-orbit --codeartifact-repository python-repository --no-internet-accessibility -u [username] -p [password] --debug
   ```

7. Deploy the Orbit Environment Stacks

   In the steps below, modify the .yaml file used for deployment with the following configuration to access the CodeArtifact configured in step 3:
   ```
   CodeartifactDomain: aws-orbit
   CodeartifactRepository: python-repository
   ```

   _The username/password here are for Dockerhub to avoid throttles_
   ```
   cd ../samples/manifests/plugins
   orbit deploy env -f ./dev-env-with-plugins.yaml -u [username] -p [password] --debug
   ```

8. Deploy the Orbit Team Stacks

   ```
   orbit deploy teams -f ./dev-env-with-plugins.yaml --debug
   ```

9. To list the Orbit environments
   ```
   orbit list env
   ```
