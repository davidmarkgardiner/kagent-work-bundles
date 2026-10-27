# Rebuild the demonstration in an office lower environment

The tested lab deployment ran a patched AgentShield Linux binary with a dedicated PostgreSQL 16 container. It reused the installed kagent and Agent Gateway. Proxmox itself is not required.

You can reproduce that host-based deployment using [the runtime guide](runtime/README.md). For Kubernetes delivery, build the patched source into an internal image and validate the container deployment in your lower environment. The container route has not been tested by this bundle.

## Image availability and the local patch

At the 27 October 2026 source check, the [official Helm guide](https://agent-shield.dev/docs/operations/helm/) says no container image is published yet. Upstream supplies a Dockerfile and Helm chart. Build an image and host it in a registry your cluster can pull from.

This demonstration also includes a small reviewed `--detector-only` patch. It starts the existing deterministic detector and finding sink without either model worker. Native kagent separately analyses the evidence through the existing chat-completions route. Upstream investigation expects a Responses-compatible endpoint. The patch is a local modification, not an upstream installation option.

The bundle contains source and patch identities, fixtures, scripts, and sanitized receipts. It contains no published patched image, prebuilt binary, or complete office-specific deployment.

## Build an image from the reviewed source

Run these commands in a new working directory with Git and Docker Buildx available. Use `linux/arm64` instead if that matches the target nodes. The upstream Dockerfile builds the web UI and Go binaries.

```bash
git clone https://github.com/davidmarkgardiner/kagent-work-bundles.git
git clone https://github.com/agentshield-dev/agentshield.git
export RUNTIME_DIR="$PWD/kagent-work-bundles/agentshield-kagent-poc/runtime"
git -C agentshield checkout b179824e455401783f031a370b8794358a10dd8c
git -C agentshield apply --check "$RUNTIME_DIR/patches/agentshield-detector-only.patch"
git -C agentshield apply "$RUNTIME_DIR/patches/agentshield-detector-only.patch"
docker buildx build --platform linux/amd64 --load \
  -t agentshield-poc:detector-only-b179824 ./agentshield
```

The build needs access to the base images and Go and JavaScript dependencies. Use approved mirrors for a restricted network. Publish the result through your internal build and image-scanning process, and record the resulting digest. A pinned source commit alone does not make the rebuilt image byte-for-byte identical to the tested binary.

Run the source tests documented in the runtime guide. Its PostgreSQL startup test requires a separate disposable test database. Validate the built image and adapted Helm rendering before deployment. The upstream chart needs adaptation to pass the local detector-only flag.

## Supply the office configuration

| Area | Required decision or value |
|---|---|
| Target | An approved lower-environment cluster and explicit Kubernetes context. |
| Images | Internal image registry, pull credentials where needed, target architecture, and reviewed digests for the detector and dummy workloads. |
| Database | Dedicated PostgreSQL 16 database, protected credentials, TLS outside loopback, and storage arrangements. |
| Observer | Dedicated read-only identity and reviewed RBAC. The default collector can read all cluster Secrets into memory. A separate demo namespace does not restrict that visibility. |
| API access | Loopback access for a host deployment, or approved authenticated access and enforced network restrictions for an in-cluster deployment. The upstream API has no authentication. |
| Discovery | Consistent cluster and source identities across the Kubernetes-backed plugins. |
| kagent | Installed version and CRDs, a compatible Agent, approved worker configuration, and the existing ModelConfig through Agent Gateway. |
| Evidence | An approved executor-local directory. Keep credentials, raw inventory, and database contents out of the repository and model prompt. |

The tested native template uses kagent `1.0.0-alpha17` and Substrate `0.6.0-alpha3` APIs. Check the office CRDs and runtime before rendering or applying it. A dedicated WorkerPool is needed only when appropriate for the installed environment. Preserve existing deployed names, authentication, routing, and delivery flow.

## Repeat the proof

Follow the full commands and ownership checks in [the runtime guide](runtime/README.md).

1. Start the dedicated database and read-only observer with the patched detector-only build.
2. Apply the owned dummy workloads, establish a reporting baseline, and activate the rule scoped to the actual dummy sensitive Pod identity.
3. Change only the Service annotation and verify no new demo finding.
4. Change the Service selector, confirm the dummy sensitive HTTP response, and verify the real persisted rule finding.
5. Use the bounded evidence packer and manually invoke one kagent session. Require an answer citing the actual finding and its limits.
6. Restore the selector. Confirm the reporting response and absence of the sensitive graph edge. Retain the historical finding and compare existing gateway and CNI configuration with the baseline.

Do not copy the lab kubeconfig, credentials, database, worker registrations, or private runtime logs into the office. Re-prove the complete flow there. This procedure establishes configuration-drift detection and assisted analysis. Blocking traffic and automatic remediation require separate proofs.
