# Reference Payload

This bundle is an operating wrapper over the existing Kagent triage v2 work
bundles. It does not need to copy every technical artifact. The work agent
should route to the relevant bundle depending on what the SRE adoption run needs.

## Related Bundles

| Need | Use |
|---|---|
| Grafana dashboards, metrics, logs, alerts | `../sre-grafana-mcp-observability/` |
| Incident evidence packs with traces/logs/metrics | `../incident-evidence-trace-log-metrics/` |
| Controlled chaos and remediation proof | `../chaos-reliability-remediation/` |
| GitLab issue, MR, docs, or GitOps change | `../gitlab-mcp-gitops-pr/` |
| KB update and querydoc/doc2vec proof | `../kagent-triage-v2-kb-gitlab-mcp/` |
| Agent-to-agent specialist fanout | `../a2a-smart-triage-workflows/` |
| Memory seeding, recall, and curation | `../memory-mcp-shared-context/` |
| Lifecycle scoring and review routing | `../lifecycle-evaluation-review-manager/` |
| HITL remediation approval | `../hitl-remediation-approval/` |
| BYO team agent onboarding | `../byo-kagent-onboarding/` |
| Policy and governance audit | `../policy-governance-safety/` |
| Fleet reporting and adoption metrics | `../aks-fleet-reporting-day2/` |

## Adoption Metrics

Track these as simple counts first. They can later become Grafana panels or
fleet report fields:

- SRE first-contact sessions completed.
- Applications/namespaces onboarded.
- Controlled exercises requested by SRE.
- Controlled exercises completed.
- Agent-assisted incidents reviewed by SRE.
- Feedback items captured.
- Feedback items converted to KB updates, skills, eval cases, dashboards, or
  policy changes.
- Improvement MRs opened and merged.
- Eval hard failures found before production.
- Remediation approvals completed or rejected.
- Adoption blockers still open.

## Feedback Categories

- missed_signal
- incorrect_triage
- weak_or_uncited_answer
- missing_kb_doc
- stale_memory
- bad_grafana_query
- missing_dashboard
- unsafe_remediation_recommendation
- unclear_handoff
- missing_workflow
- access_or_permission_blocker
- too_slow_or_too_expensive
- useful_and_should_expand

## Definition Of Adoption

Treat the workflow as adopted only when at least one SRE owner has used or
reviewed it against an application they care about, feedback has been captured,
and at least one improvement or closure action has been routed.
