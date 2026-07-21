# Work Handover Prompt: Evidence-First Worker Triage

```text
Use $evidence-first-worker-triage as the implementation work agent for a
guarded, non-production worker-to-management evidence-triage pilot. Execute
the configuration and proof; do not return a review-only answer.

## Operator prerequisites — confirm before starting

The operator must provide a private context/values file outside Git and confirm
the implementation agent is already authenticated. Do not begin deployment
until all of the following are available:

- Exact worker-cluster and management-cluster `kubectl` context names; the
  active context must be intentional, not merely the shell default.
- If read-only enrichment uses AKS MCP, its approved worker-cluster target(s),
  identity and read-only tool scope.
- One approved non-production worker namespace and the worker cluster identity
  that Alloy will stamp into every evidence envelope.
- Existing Alloy, Vector, Kafka/Confluent, Argo, kagent and GitLab locations.
- GitLab API/project configuration and the read-only kagent A2A endpoint.
- Existing Secret/CA reference names, image names/tags, service accounts,
  Kafka topic and consumer group, and the durable idempotency endpoint.

Provide references and names only—never put credential values, tokens, CA
material or private endpoints in Git or the handover prompt. If a prerequisite
is missing, report it as the blocker instead of guessing.

Start in work-agent-bundles/evidence-first-worker-triage/ and run:

  bash scripts/verify-bundle.sh

Read FRONT-SHEET.md, FLEET-TOPOLOGY.md, FABLE-FEEDBACK-RESPONSE.md, DESIRED-STATE.md,
CHECKLIST.md, STAKEHOLDER-DESIGN-DECISION.md, requests/, templates/,
payload/REFERENCE.md and evidence/EVIDENCE-TEMPLATE.md.

Before any deployment, require written owner decisions for:
- CRITIQUE_CORRECTIONS_ACCEPTED=yes
- an approved durable TTL store
- approved worker-to-management mTLS or SASL identity/rotation model
- approved data classification and retention reference
- one explicit non-production worker namespace

If a decision or value is absent, discover it from the existing target first.
Ask the owner only when it cannot be discovered safely. Do not substitute
invented credentials, endpoints or policy decisions.

Create a values file outside Git from templates/pilot-values.env.example, then
run:

  bash scripts/preflight-gates.sh --values /secure/pilot-values.env
  bash scripts/render-pilot-templates.sh --values /secure/pilot-values.env \
    --out /tmp/evidence-first-worker-triage

Review the rendered output, customise it for the existing target, run
server-side dry runs, and apply the additive configuration. The target already
has Alloy, Vector, Confluent Kafka and Argo; verify and reuse them instead of
installing duplicates.

Implement/prove only this path:

  each worker: Alloy -> worker-local Vector -> Kafka -> management validation/idempotency
  -> Argo -> read-only kagent -> idempotent GitLab work item

Do not change Alertmanager routes, Grafana alert configuration, existing
webhook/proxy integrations, production workloads, or agent permissions. Do
not enable remediation.

Capture evidence for DS-01 to DS-16, including controlled log/event delivery,
fingerprint pod-churn/distinct-signature tests, redaction scanner, DLQ,
claim-failure recovery, post-create ticket retry, stale/group replay, burst,
broker-outage and unhealthy-agent drills. Finish with the exact verdict block
from DESIRED-STATE.md and evidence/EVIDENCE-TEMPLATE.md. Create actual GitLab
work items with safe evidence when authorised; otherwise create GitLab-ready
issue files in evidence/ for the owner to copy.
```
