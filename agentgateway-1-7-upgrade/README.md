# Upgrade Agent Gateway to 1.7.0 without Substrate

Copy this folder beside `secure-byo-agentgateway-jwt-otel-amendment`, `secure-byo-agent-composition` and the existing office folders. Give the work agent [WORK-AGENT-PROMPT.md](WORK-AGENT-PROMPT.md). Merge its reviewed changes into the existing office implementation. Preserve the older bundles and their manifests.

This is a separate platform upgrade, followed by the existing secure-onboarding demo. **Run the current office demo without Substrate.** Neither Substrate installation nor actor execution is a prerequisite. Entra and dashboards remain deferred.

Start with [the human prerequisite sheet](HUMAN-PREREQUISITES.md), [release changes](RELEASE-CHANGES.md), [air-gap preparation](AIRGAP-PREREQUISITES.md), and [upgrade and rollback](UPGRADE-AND-ROLLBACK.md). The ZIP contains instructions, public artifact pins and sanitized evidence. It does not contain container images, Helm archives, credentials or an offline dependency distribution.

The home lab upgraded the secure Gateway CRD/controller Helm releases and their generated proxy, plus the existing standalone OTel model Gateway. Substrate's bundled gateways and agent runtimes stayed unchanged. See [lab evidence](evidence/lab-upgrade.json) for the exact verified scope and remaining gaps. A standalone Gateway proxy is distinct from a standalone agent Deployment.

After transfer, run `sha256sum -c SHA256SUMS` from this folder. On macOS use `shasum -a 256 -c SHA256SUMS`. Verify the reviewed GitHub revision independently. Checksums detect changed listed files, not publisher identity or extra files.
