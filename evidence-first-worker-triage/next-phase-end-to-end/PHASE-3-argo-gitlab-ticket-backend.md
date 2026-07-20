# Phase 3 — Argo backend opens GitLab tickets from agent output

**Goal:** wire the management-side Argo workflow so that **after** the read-only
kagent returns its triage analysis or remediation advice, the backend creates an
**idempotent** GitLab work item carrying that output. This is the missing
"backend" step — it currently stops at consume.

## Why

Today Argo consumes the record and the agent can run, but the value —
a ticket a human can act on — is not being created from the agent result. This
phase bakes in that last hop. The agent stays read-only: remediation is written
into the ticket as advice, never executed.

## Prompt

```text
Extend the management Argo workflow so that after the read-only triage agent
returns (triage analysis OR remediation advice), a backend step creates a
GitLab work item from that output. The ticket must be idempotent on the
incident fingerprint: the first occurrence creates, a repeat updates the open
ticket, and a long-lived incident is not re-ticketed on every replay. The
ticket body must carry the bounded, redacted evidence and the agent's
diagnosis/advice, with a workflow reference. If GitLab creation is not yet
authorised, write a GitLab-ready issue file into ../evidence/ instead, with the
exact title, labels, body, and idempotency key that would have been used. Prove
retry safety: if the workflow dies AFTER the agent returns but BEFORE the ticket
is confirmed, a retry must not create a duplicate ticket.
```

## Starting point

The backend already exists at proof level in `reference-config/03-argo.yaml`:
`claim-24h-window` (idempotency), `create-gitlab-issue` (curl to GitLab with
`PRIVATE-TOKEN`, redacted body), and update-on-duplicate. This phase **promotes**
it — swap the ConfigMap dedupe for a durable TTL store — it does not build from
zero. Read `reference-config/PROVENANCE.md`.

Do not apply `reference-config/03-argo.yaml`'s `claim-24h-window` verbatim: its
delete-then-create claim logic is non-atomic and lets two concurrent workflows
both win a claim for one incident (reproduced live as tickets #446/#447 during
Phase 0 re-proof). Use the resourceVersion-guarded compare-and-swap in
`applied-config/03-argo-augmented.yaml` instead — see
`evidence/phase0-reprove-redaction-and-correlation.md`.

## Do

1. Add the ticket-creation step to the Argo workflow **after** the agent step,
   gated on the durable TTL claim (DS-09) so only the claim owner tickets.
2. Idempotency key = incident fingerprint (DS-11). Create-or-update logic:
   open ticket exists -> update/comment; none -> create.
3. Post-create retry: kill the workflow between agent-return and
   ticket-confirm; retry; assert one ticket, not two.
4. If GitLab is not authorised yet, emit `evidence/phase3-gitlab-issue-*.md`
   files (copy-paste ready) per `../GITLAB-TICKET.md` format.

## Evidence to capture (into `../evidence/`)

- `phase3-ticket-create.md` — workflow -> agent output -> ticket URL/ID.
- `phase3-idempotency.md` — TTL claim record before/after, update-not-duplicate
  on repeat, retry-after-crash creates no duplicate.
- `phase3-agent-readonly.md` — tool inventory proving no write/apply tool.

## Done when

```text
ARGO_AGENT_READ_ONLY: yes
MANAGEMENT_TTL_IDEMPOTENCY: yes
GITLAB_TICKET_IDEMPOTENT: yes
TICKET_CARRIES_AGENT_OUTPUT: yes   # triage/remediation text present in ticket
TICKET_RETRY_NO_DUPLICATE: yes
OUTPUT_SANITIZED: yes
```
