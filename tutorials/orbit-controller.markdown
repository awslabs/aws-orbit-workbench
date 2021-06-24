---
# Feel free to add content and custom Front Matter to this file.
# To modify the layout, see https://jekyllrb.com/docs/themes/#overriding-theme-defaults

layout: documentation
title: Orbit Controller
permalink: orbit-controller
---
## Orbit Controller

---
The `orbit-controller` image contains a number of Kubernetes components. These components use pre- and post-event mechanisms to react to changes in the EKS cluster.

- __`MutatingWebhooks`__: these services receive and modify resource events before they are executed. These are __Flask__ web services managed by __Gunicorn__ listening on Port 443 and configured with TLS Certificates signed with the Certificate of the EKS Cluster, deployed as `StatefulSets`. The Certificates are managed by `cert-manager-setup-` jobs and stored in `ConfigMaps` that are mapped to the service containers. Kubernetes `MutatingWebhookConfigurations` are registered for each resource/service specific endpoint. The number of replicas in the `StatefulSet` and the number of __Gunicorn__ worker processes is configurable through the __orbit-controller-config__ `ConfigMap`. __*These are stateless services and both the number of replicas and workers can be configured.*__

- __`Watchers`__: these services monitor and react to a stream of events that have already been executed. These are CLI applications that use the Kubernetes Python SDK to continuously monitor `watcher` streams for specific Kubernetes resource types and deployed as `StatefulSets` with a replica of 1. Each service monitors and reacts to a specific stream of events, makes use of Python multi-processing workers to increase throughput, and use in-memory caches. The number of multi-processing workers is configurable through the __orbit-controller-config__ `ConfigMap`. __*These are stateful services with no mechanism for sharing state between replicase. The number of replicas should not be increased from 1.*__

### `userspace-chart-manager`

---
The `userspace-chart-manager` is a `Watcher` monitors the stream of `Namespace` resource events and manages Helm charts for individual Users.

Each time a User logs in to Orbit an `AWS Lambda` function is executed as a __PostAuthentication__ event. This Lambda is responsible for:

- determining the TeamSpaces the User belongs to from the Group membership included in the SSO Context
- creating or deleting `Namespace` resources specific to the TeamSpace/User

The `userspace-chart-manager` monitors the stream of `Namespace` events and installs or uninstalls Helm Charts for the User when TeamSpace/User specific `Namespaces` are created or deleted.

### `podsettings-pod-modifier`

---
The `podsettings-pod-modifier` is a `MutatingWebhook` that receives `Pod` CREATE and UPDATE events and applies `PodSettings` modifiers.

When the service receives a `Pod` event, it determines the TeamSpace that the `Pod` belongs to, then attempts to match the `Pod` to any `PodSettings` in the TeamSpace (the Team's `Namespace`). For each `PodSetting` that the `Pod` matches with the service applies the modifiers defined in the `spec` of the `PodSettting` to the `Pod`.

### `podsettings-poddefaults-manager`

---
The `podsettings-poddefaults-manager` service consists of two `Watchers` containers deployed in a single `Pod`: `podsettings-watcher` and `poddefaults-watcher`

#### `podsettings-watcher`

This `Watcher` monitors `PodSettings` events in the TeamSpace `Namespace`, patches the `podsettingsWatcher` key of the __orbit-controller-state__ `ConfigMap` which is used by the `podsettings-pod-modifier` to invalidate its in-memory cache of `PodSettings`, and creates a new `PodDefault` resource in the TeamSpace `Namespace` when a new `PodSetting` not labeled with `orbit/disable-watcher` is created.

The creation of the `PodDefault` in the TeamSpace `Namespace` is a trigger to the `poddefaults-watcher`.

#### `poddefaults-watcher`

This `Watcher` monitors `PodDefaults` events in the TeamSpace `Namespace` and creates copies of any new `PodDefaults` in the UserSpace `Namespaces` of all Users in the Team. These `PodDefaults` are shown as selectable configurations when Users launch new Notebooks in the Kubeflow UI.

### `pod-image-updater`

---
The `pod-image-updater` is an optional `MutatingWebhook` that receives `Pod` CREATE and UPDATE events and determines the internal ECR Image URL required for all `containers` and `initContainers` in the `Pod`. If the internal ECR URL differs from the URL on the incoming container it is updated and a new `ImageReplication` resource is created.

These new Image URLs are required when ImageReplication is enabled, either in the deployment Manifest by setting `InstallImageReplicator` to `true` or when `InternetAccessibility` is disabled.

To ensure `Pod` events are processed as quickly as possible, no check is made on the status of the Image replication. Required Image URLs are calculated and any `ImageReplication` resources are immediately created.

### `pod-image-replicator`

---
The `pod-image-replicator` is an optional `Watcher` that monitors `ImageReplication` events. When an event is receieved the service checks the state of the Image in ECR and against its in-memory cache. If the Image does not exist, is not currently being replicated, and has not failed replication 3 times, then a __CodeBuild__ task is executed to replicate the Image.