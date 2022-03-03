# **Change Log**
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
#

## **[1.6.0] - [Unreleased]**

### **Added**

### **Changed**
- FIX: added sm-operator plugin ability to pull region-specifc sm images
- FIX: updated sm-operator notebook regression test - data parsing
- FIX: updated sm-operator notebook to fetch xgboost image based off region

### **Removed**


## **[1.5.2] **

### **Added**

- New TeamEfsFsId in Team Manifest enabling team specific EFS shares
- New TeamEfsFsId support in creation of userspace
### **Changed**

### **Removed**


## **[1.5.1] **

### **Added**

### **Changed**

- FIX: moved changeset from SSM to S3 to support larger number of teams
- FIX: increased default codebuild timout
- FIX: modified SSM to support deleting more than 10 teams at once
- FIX: updated papermill to 2.3.4 in jupyter-user to fix inabilty to run lake-creator tests

### **Removed**



## **[1.5.0] **

### **Added**
- Added support for codeseeder
### **Changed**

- FIX: sleep and retry the ListPolicyTag api call after being throttled in destroy teams
- FIX: missing image ref in the README
- FIX: updated Images block in manifest - no longer referencing public ECR as default
- FIX: orbit build images funnction to update SSM on build
- FIX: deleted OIDC reference to trust policy of Admin when cluster is deleted

### **Removed**
- REMOVED software-toolkit / slrt / remotectl


## **[1.4.0] **

### **Added**

- Added orbitjob-operator and CRD
- Added schedule (cron string) to orbitjob CRD
- Added monitoring to OrbitJob so pytest can evaluate the jobs execution
- Added PyTest for lake admin, creator and user
- Added 'one-click' support for trial usage of AWS Workbench
- Added Userspace Role and RoleBinding
- Added TeamSpace operator
- Added Userspace Operator PyTest
- Added Kube-proxy and CoreDNS EKS Addons


### **Changed**

- Moved away from Job index to Status object of K8s job to report the current status
- Updated SDK to use OrbitJobs instead of Jobs and CronJobs
- Changed Lake Creator notebook
- Added sleep to Orbit SDK based OrbitJob CR job status check
- Updating README.md
- Fixed the expiring kubeconfig issue for long living k8s jobs
- Fixing lake-creator pytest shell script and refactoring lake-creator pytest files
- Removing lake user specific cron job notebooks from regression
- Removing profiles section from JL UI
- Removing lake user specific cron job notebooks from regression
- Refactored namespace controller into userspace operator
- adding userspace cr creation into post auth lambda
- ISSUE-1149: fixed landing page images/links for Chrome
- Adding env, region and team length validator to handle IAM role 64 character limit
- Updated build image, changed driver setting to overlay2

### **Removed**

- removed namespace controller deployment


## **[1.3.4] **

### **Added**
- Added support for VPC CIDR extensions (manifest boolean flag secondary_cidr)
### **Changed**

### **Removed**


## **[1.3.3] **

### **Added**
- Added tagging support for customer-managed policies in Teams  (orbit-available=true)
- ISSUE-1149: fixed landing page images/links for Chrome

### **Changed**

### **Removed**

## **[1.3.2] **

- Added orbitjob-operator and CRD
- Added schedule (cron string) to orbitjob CRD
- Added monitoring to OrbitJob so pytest can evaluate the jobs execution
- Added PyTest for lake admin, creator and user
- Added 'one-click' support for trial usage of AWS Workbench
- Added Userspace Role and RoleBinding
- Added TeamSpace operator
- Added Userspace Operator PyTest

### **Changed**
FIX - Removed the istio-system pod disruption budget before tearing down the EKS cluster. The PDB was causing a dead-lock

## **[1.3.1]**

### **Added**

### **Changed**
- FIX - support for SAML authentication
- FIX - updated logoc for AutenticatedGroups to team mappings
- FIX - changed storage-driver for build image and image replicator

### **Removed**


## **[1.3.0]**

### **Added**

- iamidentitymapping for team role to team RoleBinding and ClusterRoleBinding
- ImageReplication Operator and informative CRDs
- Opttional removal of docker credentials on env destroy
- Lens support in jupyter-user-apps
- TeamSpace CRD and Operator
- UserSpace CRD and Operator
- Added support for Path prefix to Orbit frameowork's IAM roles


### **Changed**

- FIX: overprovisioning fixed to support gpu
- FIX: force support pods (istio-system,knative-serving, etc.) to run on ENV nodes
- FIX: remove system:masters group from team -runner role mappings
- FIX: alb-ingress-controller deployment in isolated env
- FIX: fsx csi driver changes and helm chart cache refresh in the orbit-controller
- FIX: podsettings call typos
- FIX: added suppprt for sql parameters in magics (ddl and create_external_table --- database.py)
- FIX: added suppprt for  parameters in magics (run_notebooks and schedule_notebooks --- orbit.py)
- FIX: Example-6-Schedule-Notebook, removed git:// reference
- FIX: ecr repo filter logic used to delete existing env repos
- FIX: make sure Laekformation regression tests do not run in -iso envs
- REFACTOR: orbit-controller operators, webhooks, and controllers
- FIX: mpi-operator not version locked, `latest` fails to start
- FIX: Fixed the way we generate self signed certs
- FIX: Regression tests for athena notebook needs parameterized env_name in users.population_by_age table
- FIX: regression tests for DataBrew needed parameterized names
- FIX: fix podsettings filter when copying into user namespace
- FIX: imagereplication-pod-webhook patching when no changes occur
- FIX: Removed the istio-system PDB before destroying istio-system resources, causing dead-lock

### **Removed**

- REMOVED: changes to team-script-launcher...filesystem is now always used
- REMOVED: orbit profile support (use podsettings)
- REMOVED: sagemaker on eks tests for isolated envs

## **[1.2.0]**

### **Added**

- FEATURE: Added CLI support for podsettings (build and delete)
- Added MaxAvailabilityZones to foundation deployment
- Added EfaEnabled to NodeGroups
- Added AvailabilityZones filter to NodeGroups
- Manifest validator to check the managed node group desired number of nodes value
- Added support for `Custom Domain Name` attribute to point Orbit using custom dns
- Added support for externally providing `SSL CertArn`
- Added Multi stage Orbit deployment ability

### **Changed**

- REFACTOR: Moved the path of installation of VSCode to /home/jovyan/.code-server
- FIX: nodes_subnets vs private_subnets inconsistencies
- UPDATED: nvidia daemonset version
- UPDATED: vpc-cni version
- FIX: replace cert-manager/jobs with cert-manager/certifactes
- FIX: remove the ownerReference on userspace PodDefaults (because they're in the teamspace namespace)
- FIX: yaml parameter replacement regex
- REFACTOR: modified overprovisioning plugin to leverage nodeSelector for application to nodeGroups
- FIX: greedy bucket deletion by prefix when destroying
- FIX: jupyter-webapp custom configmap
- FIX: configured team_scrip_launcher to optinally add an FS mount
- FIX: clean-lakeformation-glue-database does not user fs, added in lighter image
- FIX: restart SSM Agent DaemonSet after image replication
- UPDATED: python packages and dependencies
- UPDATED: Fsx Lustre serviceaccount IAM role policy change to allow fsx resource tagging
- FIX: force alb-controller in kubeflow to use env nodes
- FIX: redshift plugin describe cluster based on specific env and team tags
- FIX: added region to team when deploying plugins
- FIX: enable manifest generation from cli

### **Removed**
-- REMOVED: call to install ~/.kube/config


#
## **[1.1.0]**
#
### **Added**

- SSO property in the plugin manifest.
- Adding demo notebooks cron jobs cleaner job.
- Made CodeArtifact Domain and Repository creation mandatory from foundation/environment if the user wont specify it.
- Script to deploy a demo
- Adding lakeformaton controlled database cleanup job
- Adding orbit admin role actions wrt emr-containers list and cancel jobs to allow virtual cluster deletion
- Added inventory of known images to image-replicator
- New initContainer on image-replicator primes environment by replicating inventory
- Added `deploy/destroy toolkit` command to CLI
- Added `deploy/destroy credentials` command to CLI
- Added multi-registry docker login to code-build-image
- Added Credential store in Secrets Manager for Docker credentials
- Enabled AWS_STS_REGIONAL_ENDPOINTS env variable on kubeflow Pods
- Enable/Disable WAF on ALB Controller dependent on internet-accessibility
- Added orbit/applied-podsettings annotation to Pods when PodSetting is applied
- Added podsetting support in regression notebooks and sdk
- Added Fargate Profile for kubeflow/istio-system Pods when deploying in isolated subnets
- Track Orbit usage

### **Changed**

- FIX: podsettings-pod-modifier wasn't applying resources to pods
- FIX: Fixed the cleanup of cognito pools.
- FEATURE: podsettings for teams implementation
- FIX: code-build-image defaults to legacy dependency resolver
- FIX: `--force-deletion` on kubeflow destroy, rather than another deploy
- FIX: added new `iam:TagOpenIDConnectProvider` permission to admin role
- FIX: istio-ingress wait/polling issuses
- FEATURE: orbit-system is first namespace deployed to enable environment manipulation
- FIX: SMLog support for users of Sagemaker Operators
- FIX: Added default values to pull kubectl in the k8s-utilities image
- FIX: Increase cluster-autoscaler resource limits
- FIX: image-replicator fails if unable to prime env from image inventory
- FIX: reset the resource_version in the orbit-controller when watch dies gracefully
- FIX: reduce destroy time by selectively removing k8s resources
- FIX: landing-page-service liveness and readiness probes in isolated subnet
- FIX: landing-page-service into Fargate task in isolated subnet
- FIX: fixed the issue of ray workers not joining ray head
- FIX: reduced the sleep time for resources deletion between user spaces
- FIX: Added `AuthenticationGroups` to the manifest.yaml under samples
- FIX: cleanup of istio-ingress raises exception when no cluster exists
- FIX: remove the ownerReference on userspace PodDefaults (because they're in the teamspace namespace)

### **Removed**

- Docker credentials from `foundation` and `env` commands
- S3 Docker credential store
- Duplicate cluster-autoscaler manifest creation