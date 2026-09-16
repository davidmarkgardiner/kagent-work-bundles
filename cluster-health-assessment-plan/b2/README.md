# B2 cross-cluster snapshot transfer

This lab implementation sends only the worker's latest bounded snapshot to a separate agent-cage Kubernetes API server. It uses HTTPS with a private CA, HMAC request authentication, a trusted cluster/generation binding, a 256 KiB intake limit, and monotonic PostgreSQL replacement. It does not share a filesystem or database credential with the worker.

The worker publisher has only `get` access to ConfigMaps in `cluster-health-system`. It has no Secret read, pod list, exec, or workload-write permission. A failed publication cannot stop the B1 collector and the publisher has no historical spool.

The public manifest contains `https://agent-cage.example.invalid:30443`. Set the real endpoint through a private environment overlay. Create the runtime CA, TLS, HMAC, database, and internal-client Secrets through the approved secret manager; never commit them.

The original plan proposed Kafka. Direct authenticated HTTPS was selected for the accelerated homelab build because it proves the required trust boundary and latest-state semantics with fewer moving parts. A workplace Kafka state lane remains a supported environment-specific replacement; do not claim Kafka evidence from this lab result.

Run `../verify-all.sh {{WORKER_CONTEXT}} {{AGENT_CAGE_CONTEXT}}` for static, render, server-dry-run, public-safety, and RBAC checks. Live drills and their exact limitations are in [the evidence receipt](../evidence/2026-09-15-accelerated-lab.md).
