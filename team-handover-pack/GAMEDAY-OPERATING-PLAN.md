# Game-Day Operating Plan

## Purpose

Use controlled lower-environment exercises to turn Kagent triage v2 from a
platform feature into an SRE operating habit.

The point is not to prove chaos for its own sake. The point is to test whether
SRE can use the workflow, trust the evidence, challenge weak answers, and feed
improvements back into the platform.

## Proposed Cadence

Start small:

- 1 session per week for 4 weeks.
- 60-90 minutes per session.
- 1 SRE owner or pair per session.
- 1 application or namespace per session.
- 1 controlled lower-env scenario per session.

After the first month, decide whether to continue weekly, move to fortnightly,
or fold into existing reliability/incident review ceremonies.

## Session Flow

1. Pick application or namespace.
2. Confirm owner, approval route, and lower-env scope.
3. Run first-contact prompt if this app is new.
4. Choose one safe failure mode.
5. Validate the game-day request.
6. Inject or simulate the failure.
7. Use Kagent triage v2 through the approved front door.
8. Collect Grafana/GitLab/KB/memory/eval/HITL evidence.
9. Ask SRE whether the answer was correct, useful, and safe.
10. Route at least one improvement item or record that none was needed.

## Starter Scenarios

| Scenario | Target | Expected evidence | Remediation boundary |
|---|---|---|---|
| Pod delete | Lower-env deployment | pod restart, events, logs, metrics | Usually observe/recover; no manual remediation unless failure persists |
| Crashloop | Lower-env workload with controlled bad config | CrashLoopBackOff, logs, restart count, dashboard panel | Fix through GitLab MR or approved workflow |
| Missing dependency | Lower-env service dependency or config | failed readiness, logs, connection metrics | HITL before config/workload changes |
| Cert-manager failure | cert-manager lower-env object | Certificate/Issuer status, events, logs | Read-only triage; GitOps/HITL for changes |
| Alert replay | Existing alert payload | alert route, dedup behavior, A2A fanout | No cluster mutation |

## Feedback Questions

- Did the agent identify the right affected resource?
- Did it attach enough Grafana evidence?
- Did it cite KB/docs where relevant?
- Was the recommendation safe?
- Was the proposed remediation actionable?
- Was the lifecycle eval fair?
- What would SRE need to trust this in a real incident?
- Which skill, KB doc, dashboard, query, policy, or workflow should change?

## Success Measures

- SRE-run or SRE-reviewed sessions completed.
- Apps/namespaces onboarded.
- Feedback items captured.
- Improvements routed and closed.
- Eval hard failures caught.
- Evidence packs created.
- Remediation approvals completed or denied with identity.
- Open blockers with owners.

## Guardrails

- Lower-env only unless formally approved.
- No production chaos by default.
- Diagnostic/front-door agents stay read-only.
- Remediation requires HITL or GitOps review.
- Evidence must be sanitized.
- Missing tools/datasources are blockers, not proof.
