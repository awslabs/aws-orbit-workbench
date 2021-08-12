# **Change Log**
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
#
## **[1.2.0] - Unreleased**
### **Added**
### **Changed**

- REFACTOR: Moved the path of installation of VSCode to /home/jovyan/.code-server
- FIX: replace cert-manager/jobs with cert-manager/certifactes
- FIX: remove the ownerReference on userspace PodDefaults (because they're in the teamspace namespace)

### **Removed**


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

### **Removed**

- Docker credentials from `foundation` and `env` commands
- S3 Docker credential store
- Duplicate cluster-autoscaler manifest creation