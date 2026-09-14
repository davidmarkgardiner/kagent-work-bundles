# AKS incident management bundle

## Outcome

Provide a repeatable, local-first incident workflow that accepts a canonical alert, asks a read-only kagent to investigate the affected cluster, publishes an audit ticket and optional GitOps merge request, pauses for up to 72 hours, and executes only the exact approved action through a separate write identity.

## Operators and boundaries

The platform SRE team installs the bundle in a management cluster. Existing Alloy or Vector pipelines publish normalized incidents to Kafka. Argo Events starts one Workflow per incident. The coordinator owns incident state and approval binding; kagent remains the reasoning layer. Postgres is the durable system of record. GitLab, Teams, and ServiceNow are integrations, not state stores.

Investigation and execution are deliberately separate:

- the investigator has read-only Kubernetes MCP tools;
- the coordinator cannot mutate Kubernetes or merge code;
- the executor has only allow-listed write tools and credentials;
- approval names an action id, action type, target, and resource version or commit SHA;
- expired, replayed, changed, or rejected approvals fail closed.

## First two production flows

1. Direct remediation: investigate, open/update the incident ticket, request approval, resume the suspended Workflow, apply one bounded Kubernetes change, verify it independently, then update the same ticket and notify the SRE channel.
2. GitOps remediation: investigate, create an incident branch and draft merge request, request approval for the exact MR SHA, resume the Workflow, merge only that SHA after required checks, verify reconciliation, then update the same ticket and notify the SRE channel.

## Acceptance criteria

- Duplicate Kafka deliveries converge on a stable incident fingerprint and do not duplicate writes.
- An incident cannot execute before an authenticated approval.
- An approval cannot be reused for a different action, target, or version.
- Investigation works when the executor is absent or disabled.
- The 72-hour timeout leaves the incident unexecuted and records expiry.
- GitLab issue, approval, execution, and verification receipts share the incident id.
- The supplied OOM/GitOps and missing-label/direct-remediation fixtures pass locally.
- Rendered manifests contain no unresolved placeholders or literal credentials.
- Public-safe scan, application tests, YAML parse, and Kubernetes client dry-run pass before hand-off.

## Explicit non-goals

This bundle does not install Confluent, an enterprise Teams bot, ServiceNow credentials, GitLab credentials, kubeconfigs, or a production model. It defines and validates those interfaces. Redpanda is the no-cost local Kafka-compatible option; Confluent remains the production transport.

## Delivery gate

The bundle may be built and validated locally. Publishing its image, creating work tickets or merge requests, and applying it to a work cluster are separate approvals.
