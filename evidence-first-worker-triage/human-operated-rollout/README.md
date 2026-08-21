# Human-Operated Worker-to-Management Rollout

This folder is for a human operator who wants to install and prove the
evidence-first triage path one component at a time:

```text
worker cluster: Alloy -> Vector -> Confluent Kafka
management cluster: Kafka -> Argo EventSource/Sensor -> Workflow
                    -> read-only kagent + AKS MCP -> GitLab work item
```

It is intentionally separate from the implementation-agent handoff. Use the
existing pilot overlay and proven configs as references, but never copy their
namespaces, images, Secrets, topics, consumer groups or labels verbatim.

## Start here

1. Copy `values.env.example` to a private `values.env` outside Git. Put only
   context names, resource references and approved image references in it—never
   credentials. Every script derives environment-specific names from this file.
   For the manual commands in the guides, load that trusted file first with
   `set -a; source /path/to/private/values.env; set +a`.
2. Read [01-WORKER-ALLOY-VECTOR-KAFKA.md](01-WORKER-ALLOY-VECTOR-KAFKA.md) and
   complete the worker side first. Do not configure Argo until a controlled
   marker is demonstrably accepted by Kafka.
3. Read [02-MANAGEMENT-ARGO-WORKFLOW.md](02-MANAGEMENT-ARGO-WORKFLOW.md) and
   prove the EventSource receives that Kafka payload and creates a workflow.
4. Complete [03-TRIAGE-QUALITY-AND-DAILY-SMOKE.md](03-TRIAGE-QUALITY-AND-DAILY-SMOKE.md):
   ticket quality, read-only AKS MCP proof, active smoke cases, and the
   promotion criteria for a daily scheduled test.

## Non-negotiable safety rules

- Run `kubectl config current-context` and use the explicit `--context` shown
  by the scripts. A shell's default context is never sufficient proof.
- Discover current images, CRDs, service accounts, namespaces, Secret
  references, EventSources and Flux/GitOps ownership before rendering/applying.
  The local `reference-config/` and `applied-config/` folders are evidence, not
  install manifests for work.
- Keep the agent and AKS MCP read-only. The agent can diagnose and open a
  ticket; it must not apply, delete, patch, exec, restart, scale or remediate.
- Start with one approved non-production namespace. Do not alter Alertmanager,
  Grafana alert routes or existing production consumers.
- Stop at the failed boundary. A green downstream component does not prove an
  earlier component was healthy.

## Scripts

All scripts are read-only and take a private values file:

```bash
bash scripts/check-worker-alloy-vector.sh --values /path/to/private/values.env
bash scripts/check-management-argo.sh --values /path/to/private/values.env
bash scripts/check-triage-and-tools.sh --values /path/to/private/values.env --workflow {{WORKFLOW_NAME}}
```

They inspect resource state, logs and reference wiring. They do not install,
restart, mutate, reset offsets or print Secret values.

The values file is deliberately explicit: worker/management contexts and
namespaces; Alloy/Vector deployments, service, PVC and expected images;
EventBus/EventSource/Sensor/WorkflowTemplate names and selector/image;
kagent/AKS MCP names, selectors and image; and the approved Kafka topic/group.
The scripts fail when a required resource or expected image does not match.

## References reused by this guide

- [Pilot Kustomize overlay](../kustomize/overlays/pilot/)
- [Manual pilot checklist](../kustomize/overlays/pilot/MANUAL-RUN-CHECKLIST.md)
- [End-to-end proof/reference config](../next-phase-end-to-end/reference-config/PROVENANCE.md)
- [Applied correctness fixes](../next-phase-end-to-end/applied-config/README.md)
- [Component verification and deduplication tests](../next-phase-end-to-end/component-verification/README.md)
- [Sanitized real home GitLab ticket example](examples/home-triage-gitlab-ticket-example.md)
- [Source-aware Vector, Argo and ticket amendment](examples/source-aware-payload-and-ticket-amendment.md)
- [Management kagent AKS-MCP-only investigation contract](examples/management-aks-mcp-only-investigation.md)
- [AKS-MCP workload-identity refresh diagnostic](examples/aks-mcp-workload-identity-refresh-diagnostic.md)
- [Workflow lifecycle and shared Kafka routing contract](examples/workflow-lifecycle-and-shared-kafka-routing.md)
- [24-hour deduplication and noise-control contract](examples/deduplication-24h-noise-control.md)
- [Agent smoke-test bundle](../../agentic-triage-smoke-tests/README.md)
- [Deterministic agent evals](../../../observability/agent-evals/README.md)
