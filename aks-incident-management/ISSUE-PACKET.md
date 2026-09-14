# Implementation issue packet

## Epic: approval-bound incident remediation

### IM-1 — Runtime and durable state

Build the coordinator image, Postgres-backed incident registry, health endpoints, audit timeline, stable fingerprint deduplication, and recovery of interrupted investigations.

### IM-2 — Event intake

Connect the canonical `incident.v1` Kafka topic to the Argo EventSource and Sensor. Validate SASL/TLS configuration against Confluent. Retain a Redpanda overlay for local smoke tests.

### IM-3 — Read-only investigation

Connect the coordinator to the existing kagent A2A endpoint and read-only Kubernetes MCP agent. Prove the agent cannot see write tools and preserve complete evidence in the incident record.

### IM-4 — GitLab and ServiceNow outputs

Configure the GitLab MCP project allow-list. Connect the existing ServiceNow integration relay. Prove idempotent update of one record per incident fingerprint.

### IM-5 — Teams approval callback

Connect the existing Teams bot to the documented request/callback contract. Authenticate callbacks, record the resolved human identity, enforce 72-hour expiry, and reject replays.

### IM-6 — Bounded execution

Deploy the executor with a distinct ServiceAccount and RemoteMCPServer. Start with the label patch and exact-SHA GitLab merge tools. Add new remediation tools one at a time with resource-name RBAC and a deterministic verifier.

### IM-7 — Production acceptance

Run both fixtures in non-production, capture Kafka produced/consumed evidence, Argo node state, kagent tool trace, issue/MR links, approval identity, exact mutation receipt, and post-change verification. Obtain security and platform-owner sign-off before production enablement.
