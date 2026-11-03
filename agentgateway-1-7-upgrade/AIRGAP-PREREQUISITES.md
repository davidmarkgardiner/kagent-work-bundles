# Prepare the offline artifacts first

The office cannot pull public images. Use [artifact inventory](artifact-inventory.json) as a source reference for the connected acquisition/build process. The ZIP itself supplies no binary artifacts. Import and approve the complete prerequisite set before dependent deployment.

1. Identify target architectures, installed owners, current versions and rollback requirements. Reuse a compatible Kubernetes/Gateway API installation. Check kubectl/API-server version skew and obtain a compatible approved CLI if needed. Do not reinstall kagent, Kyverno, the collector or Substrate for this upgrade.
2. Through the approved connected process, acquire the exact 1.7 controller/proxy images and CRD/controller Helm charts. Obtain `agentgateway-standalone` only if that chart is the existing standalone proxy owner. Preserve signatures/provenance required by the organization.
3. Transfer/import charts and images through the approved boundary. Retain source index digest, platform manifest digests, destination references/digests, transfer hashes and importer receipt. Mirroring can change manifests; a source digest is not automatically the destination digest.
4. Verify every required platform and every rendered init/sidecar image. Retain matching current-version images/charts for rollback. Do not use floating tags or assume the two core images cover an office customization.
5. Render with internal registries and digest-pinned images. Set the controller image and generated proxy image separately. An existing per-Gateway override can prevent the controller chart's proxy default from taking effect. Inspect the actual generated Deployment after reconciliation.
6. Disable public catalog refresh and use approved catalogs, identity endpoints, models and MCP servers. Work must not run public `helm pull`, `docker pull`, installer scripts or package downloads. Installed Helm/kubectl need no additional Python packages for these instructions.

For a connected acquisition host, the public chart coordinates are `oci://cr.agentgateway.dev/charts/agentgateway` and `oci://cr.agentgateway.dev/charts/agentgateway-crds`, both version `v1.7.0`. They are acquisition references only, not office deployment commands. Use verified local `.tgz` archives or an approved internal OCI registry inside work.

The lab's first direct `kind load docker-image` attempt failed because its image store referenced unavailable platform content. Exporting only `linux/amd64` with `docker image save --platform linux/amd64`, then using `kind load image-archive`, passed. This is a lab import detail, not an AKS prerequisite or a substitute for verifying destination manifests.

The existing `otel-agent-flow` chart uses `gatewayImage`. Update the maintained office values/lock and add the reviewed session Secret/env reference where needed. Do not rerun its older platform installer; it upgrades unrelated native components and is outside this task.
