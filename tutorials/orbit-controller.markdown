---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Orbit Controller
permalink: orbit-controller
---
## Orbit Controller

The `orbit-controller` image contains a number of Kubernetes components. These components use pre- and post-event mechanisms to react to changes in the EKS cluster.

- `MutatingWebhooks`: these services receive and modify resource events before they are executed. These are __Flask__ web services managed by __Gunicorn__ listening on Port 443 and configured with TLS Certificates signed with the Certificate of the EKS Cluster, deployed as `StatefulSets`. The Certificates are managed by `cert-manager-setup-` jobs and stored in `ConfigMaps` that are mapped to the service containers. Kubernetes `MutatingWebhookConfigurations` are registered for each resource/service specific endpoint. The number of replicas in the `StatefulSet` and the number of __Gunicorn__ worker processes is configurable through the __orbit-controller-state__ `ConfigMap`. __*These are stateless services and both the number of replicas and workers can be configured.*__

- `Watchers`: these services monitor and react to a stream of events that have already been executed. These are CLI applications that use the Kubernetes Python SDK to continuously monitor `watcher` streams for specific Kubernetes resource types and deployed as `StatefulSets` with a replica of 1. Each service monitors and reacts to a specific stream of events, makes use of Python multi-processing workers to increase throughput, and use in-memory caches. The number of multi-processing workers is configurable through the __orbit-controller-state__ `ConfigMap`. __*These are stateful services with no mechanism for sharing state between replicase. The number of replicas should not be increased from 1.*__

### `userspace-chart-manager`

This `Watcher` monitors the stream of `Namespace` resource events and manages Helm charts for individual Users.

Each time a User logs in to Orbit an `AWS Lambda` function is executed as a __PostAuthentication__ event. This Lambda is responsible for:

- determining the TeamSpaces the User belongs to from the Group membership included in the SSO Context
- creating or deleting `Namespace` resources specific to the TeamSpace/User

The `userspace-chart-manager` monitors the stream of `Namespace` events and installs or uninstalls Helm Charts for the User when TeamSpace/User specific `Namespaces` are created or deleted.

### `podsettings-pod-modifier`

This `MutatingWebhook`