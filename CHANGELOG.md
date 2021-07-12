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

### **Changed**

- FIX: podsettings-pod-modifier wasn't applying resources to pods
- FEATURE: podsettings for teams implementation
