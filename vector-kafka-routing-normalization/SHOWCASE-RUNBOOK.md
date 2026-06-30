# LGTM To Agentic Resolution Showcase Runbook

This is the one-path demo runbook for stakeholders and work-side operators. It
uses the Vector routing bundle plus Grafana, Argo, specialist agents, and ticket
evidence to prove the full alert-to-resolution lifecycle.

## Story

```text
controlled fault
  -> LGTM / Grafana alert fires
  -> contact point delivers event
  -> Kafka raw topic or Vector HTTP receiver
  -> Vector normalizes, dedupes, and routes
  -> Kafka normalized topic
  -> Argo EventSource and Sensor
  -> Argo Workflow
  -> specialist agent
  -> evidence pack
  -> GitLab or ServiceNow ticket
  -> optional HITL remediation
  -> Grafana dashboard shows outcome
```

## Before The Demo

Confirm:

- Grafana MCP or API fallback can create/update test alert rules.
- The chaos alert rules exist in the `Kagent Chaos Gameday` folder.
- Rules are paused until the approved test window.
- Vector is healthy and publishing `observability.triage.v1`.
- Argo EventSource and Sensor are consuming the normalized topic.
- The ticket target is a test GitLab project or ServiceNow queue.
- Remediation is default-deny unless HITL approval is explicitly part of the
  demo.

## Golden Path

1. Open the Grafana showcase dashboard.
2. Select one scenario from [`scenarios/SCENARIO-PACK.md`](scenarios/SCENARIO-PACK.md).
3. Unpause only the matching Grafana alert rule.
4. Inject the controlled fault in the approved namespace.
5. Watch the alert enter firing state.
6. Confirm Vector emits one normalized event with:
   - `schema_version`
   - `target_agent`
   - `route_key`
   - `routing_reason`
   - `dedupe_key`
7. Confirm Argo creates the triage workflow.
8. Confirm the workflow calls or records the expected specialist agent.
9. Confirm the ticket contains the evidence contract.
10. Roll back the fault.
11. Confirm alert resolution or recovery evidence.
12. Record the dashboard link and workflow/ticket IDs.

## What To Say

This is not just alert forwarding. The platform is proving:

- durable event capture or a documented direct receiver path
- normalized contracts before automation
- routeable specialist-agent workflows
- duplicate suppression before workflow creation
- evidence-backed tickets
- human gates before write-capable remediation
- measurable outcomes in Grafana

## Pass Criteria

The showcase passes when:

- one scenario fires from Grafana/LGTM
- Vector selects the expected route
- Argo creates a workflow from the normalized topic
- the expected specialist agent is selected
- a ticket or evidence record is created
- rollback is verified
- the dashboard shows the run

Use [`PROMOTION-GATE.md`](PROMOTION-GATE.md) before claiming the path is ready
for wider rollout.
