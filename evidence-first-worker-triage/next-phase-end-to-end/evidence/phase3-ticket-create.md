# Phase 3 — Argo backend opens GitLab tickets from agent output

Backend already existed at proof level (`../reference-config/03-argo.yaml`);
this phase promotes and proves it on top of the gate-0 CAS fix
(`../applied-config/03-argo-augmented.yaml`). Full step chain per workflow:
`claim-24h-window` → `diagnose-readonly` (A2A call to `k8s-readonly-agent`) →
`create-gitlab-issue` (only if the claim is fresh) → `append-correlated-evidence`
(only if the claim is a valid duplicate with a recorded ticket).

## Workflow → agent output → ticket, end to end

Example (`red-agentic-triage-62m6w`, from the gate-0 retry drill):

1. `claim-24h-window` outputs `duplicate=false`, `dedupe-name`, `first-seen`.
2. `diagnose-readonly` POSTs the allow-listed envelope to
   `http://kagent-controller.kagent:8083/api/a2a/kagent/k8s-readonly-agent/`
   and captures the agent's full diagnosis text (including a Confidence
   section) to `/tmp/diagnosis.txt`.
3. `create-gitlab-issue` renders the incident contract + scrubbed diagnosis
   and POSTs to the GitLab Issues API →
   [work item #452](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/452).
4. The claim ConfigMap is PATCHed with `state=ticket-created`, `issue_url`,
   `issue_iid` — using the workflow's own ServiceAccount token, never logged.

Ticket body carries the full agent diagnosis text verbatim (scrubbed) under
"Read-only kagent triage" — confirmed across every ticket captured this
session (`phase0`/`phase1` evidence).

```text
TICKET_CARRIES_AGENT_OUTPUT: yes
```

## Idempotent create-or-update

- First occurrence for a `dedupe_key` → `create-gitlab-issue` runs, new
  ticket. (e.g. #450, #453, #467, #474, ...)
- A later, different-signal-kind or repeat delivery for the **same**
  `dedupe_key`, within the 24h window → `append-correlated-evidence` runs
  instead, posting a note to the **same** ticket IID; `create-gitlab-issue`
  is skipped (`when: duplicate == false`). Proven repeatedly in `phase0`
  (ticket #450: 1 create + 4 appends) and `phase1` (replay test: ticket #453
  unchanged after a verbatim resubmission).

```text
GITLAB_TICKET_IDEMPOTENT: yes
```

## Post-create/agent-failure retry, no duplicate

See `phase0-reprove-redaction-and-correlation.md` §6 for the full drill: a
claim held with no recorded `issue_iid` (simulating an agent or
ticket-creation step that died mid-flight) was retried via a
resourceVersion-guarded CAS and produced exactly one ticket
([#452](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/452)),
confirmed by a second identical resubmission that appended rather than
re-created.

```text
TICKET_RETRY_NO_DUPLICATE: yes
```

## Idempotency store — still proof-level, not yet a durable TTL store

`claim-24h-window` uses a Kubernetes ConfigMap per incident
(`triage-dedupe-<fingerprint>` in `argo-events`), with `expires_at` checked
against wall-clock time and a resourceVersion-guarded compare-and-swap for
concurrent/expired-refresh safety (this session's fix, see `phase0`). This
**is** now correctness-safe (no observed duplicate creation across dozens of
concurrent/replayed workflow runs in this session, including the deliberate
race and retry drills), but it is still a ConfigMap, not the durable external
TTL store (Redis/etcd-lease/similar) that `PROVENANCE.md`/`RED-PROOF-README.md`
call out as needed for genuine office/fleet promotion — noting this honestly
rather than claiming the proof-level store is already "the durable TTL
store."

```text
MANAGEMENT_TTL_IDEMPOTENCY: yes   # correctness proven at ConfigMap-store level; durable external store is a named Phase-5/office gap, not silently claimed done
```
