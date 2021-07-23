# **Change Log**
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
#
## **[1.1.0] - Unreleased**
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

### **Removed**

- Docker credentials from `foundation` and `env` commands
- S3 Docker credential store
- Duplicate cluster-autoscaler manifest creation


