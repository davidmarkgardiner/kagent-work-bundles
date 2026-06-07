# GitLab Ticket: Run Controlled Chaos Remediation Proof

## Summary

Run one approved lower-environment chaos scenario and prove Kagent can triage,
gate remediation, verify recovery, and report evidence.

## Feature

SRE should be able to request a controlled failure and see the triage platform
collect evidence, propose safe remediation, require approval, and report the
outcome.

## Evidence Required

- Runtime readiness result.
- Approved target and blast-radius note.
- Chaos injection record.
- Grafana/cluster evidence.
- HITL or GitOps approval boundary.
- Recovery proof.
- Lifecycle eval/report.

## Acceptance Criteria

- `CHAOS_REQUEST_ACCEPTED: yes`
- `TARGET_NON_PROD: yes`
- `CHAOS_INJECTED: yes`
- `TRIAGE_STARTED: yes`
- `GRAFANA_EVIDENCE_ATTACHED: yes`
- `HITL_REQUIRED_FOR_REMEDIATION: yes`
- `RECOVERY_VERIFIED: yes`
- `LIFECYCLE_EVAL_RECORDED: yes`
- `REPORT_CREATED: yes`
- `OUTPUT_SANITIZED: yes`

## Notes

Do not run production chaos. Stop if runtime readiness, target opt-in, or
approval routing is not proven.
