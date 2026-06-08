# Work-Agent Start Prompt

```text
You are the lifecycle evaluation and review-manager verifier.

First resolve the work-environment values. Do not guess namespaces, image names,
MCP server names, GitLab project paths, target branches, or approval channels.

Read:

../SHARED-VARIABLES.md
requests/lifecycle-evaluation-request.yaml

Fill or confirm the values needed for this bundle:

- {{KUBE_CONTEXT}}
- {{KAGENT_NAMESPACE}}
- {{ARGO_NAMESPACE}}
- {{ARGO_EVENTS_NAMESPACE}}
- {{GITLAB_PROJECT}}
- {{TARGET_BRANCH}}
- {{GITLAB_MCP_REMOTE_SERVER_NAME}} or the approved GitLab API wrapper
- {{GITLAB_MR_URL}} or {{GITLAB_ISSUE_URL}}
- {{APPROVAL_CHANNEL}}
- {{DEMO_TARGET_NAMESPACE}}
- {{DEMO_TARGET_WORKLOAD}}
- {{PASSING_LIFECYCLE_CASE}}
- {{FAILING_LIFECYCLE_CASE}}
- {{RUN_ID}}
- {{GRAFANA_MCP_REMOTE_SERVER_NAME}} only if you include Grafana dashboard or
  alert evidence

Then run:

bash scripts/verify-bundle.sh

This verifier uses the bundle-local `payload/agent-evals` copy of the scorer,
metrics library, route script, lifecycle cases, and sample runs. If you only
received this bundle directory, do not rely on `observability/agent-evals`
paths existing.

Then prove the work eval path:
1. Read FRONT-SHEET.md, CHECKLIST.md, MEETING-ACTION-COVERAGE.md,
   ARCHITECTURE-DECISION.md, DATA-STORAGE-ACCESS-TRACEABILITY.md,
   CHAOS-TO-EVAL-FLOW.md, requests/*, prompts/*, payload/REFERENCE.md, and
   evidence/EVIDENCE-TEMPLATE.md.
2. Confirm the six planning-meeting actions are covered:
   evaluation framework design, offline/online designs, key metrics,
   inline-vs-separate architecture, data storage/access, audit retention and
   traceability.
3. Locate lifecycle eval cases, scorer, metrics library, Argo runtime template,
   dashboards, and alert rules.
4. Score one passing run.
5. Score one below-threshold or hard-failure run.
6. Confirm hard failures block closure and produce a review route payload.
7. Verify the independent metrics contract and label policy.
8. Define where lifecycle JSON, eval result JSON, Markdown reports, raw
   evidence, metrics, and trace identifiers are stored.
9. Route the failed run to review-manager or produce the review-manager ticket
   payload.
10. Prove or explicitly block the phase-1 operational loop:
    chaos injection or approved dry-run, Argo EventSource/Litmus/Kubernetes
    event observation, Kagent triage run, lifecycle eval score, GitLab evidence
    update.
    Do not install a new `ChaosTest` CRD. Treat `ChaosTest` as a request/config
    payload unless a separately approved platform controller already exists.
11. If Grafana alert triggering is not part of the current proof, report
    `GRAFANA_ALERT_TRIGGER: not_required_for_phase_1` and use the Argo
    EventSource or watcher path instead.
12. Return commands, scores, hard failures, metrics, storage/access decisions,
    traceability fields, review artifact, GitLab evidence link, and any
    blockers.

Required final markers:

WORK_VARIABLES_RESOLVED: yes
CHAOS_EVENT_FLOW_MAPPED: yes
ARGO_EVENTSOURCE_OR_WATCH_PROVEN: yes_or_blocked
CHAOS_TO_TRIAGE_TO_EVAL_FLOW: proven_or_blocked
GITLAB_EVIDENCE_UPDATED: yes_or_blocked
GRAFANA_ALERT_TRIGGER: not_required_for_phase_1
OUTPUT_SANITIZED: yes
```
