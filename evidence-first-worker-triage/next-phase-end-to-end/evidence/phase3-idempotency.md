# Phase 3 — Idempotency: claim state before/after, update-not-duplicate, retry-after-crash

## Claim record, before/after a repeat delivery (in-window)

Before replay (`../evidence/phase1-smoke-tests.md` replay test, dedupe key
`d726e032...`, ticket #453):

```json
{"dedupe_key":"d726e032...","expires_at":"1784632229","first_seen":"2026-07-20T11:10:29Z","issue_iid":"453","issue_url":".../453","signal_kind":"event","state":"ticket-created"}
```

After resubmitting the exact same incident envelope via
`argo submit --from workflowtemplate/red-agentic-triage`:

```json
{"dedupe_key":"d726e032...","expires_at":"1784632229","first_seen":"2026-07-20T11:10:29Z","issue_iid":"453", ...}   # unchanged
```

`issue_iid` unchanged, `expires_at` unchanged (the duplicate branch does not
touch the claim at all) — the workflow logged `"24-hour duplicate
suppressed"` and only ran `append-correlated-evidence`.

## Update-not-duplicate under a genuine race (gate 0, dedupe key `b5d7b30a...`)

| Step | Claim state | Ticket |
|---|---|---|
| `red-event-triage-tpdqw` (BackOff, first) | claim created | **#450 created** |
| `red-log-triage-9cgm7` (log, arrives after) | duplicate (has issue_iid) | appended to #450 |
| `red-event-triage-jpq97`, `9tp85` (BackOff repeats) | duplicate | appended to #450 |

One ticket, three appends, correct ordering-independence (see `phase0` §3
for the full before/after and the race this was found to have in the
original, unfixed claim script).

## Retry-after-post-create/agent failure (drill, gate 0 §6)

| State | Claim | Ticket |
|---|---|---|
| Simulated failure: claim exists (`state=claimed`), no `issue_iid` | pre-created manually | none yet |
| First retry submission | CAS-guarded retry-claim wins, `state=claimed-retry` → `ticket-created` | **#452 created**, `first_seen` preserved from pre-failure claim time |
| Second identical submission | `duplicate=true` (has issue_iid now) | appended to #452, `issue_iid` unchanged |

```text
# (duplicated here from phase0/phase3-ticket-create.md for this file's own completeness)
GITLAB_TICKET_IDEMPOTENT: yes
TICKET_RETRY_NO_DUPLICATE: yes
```

## Retry-after-ticket-created-but-claim-unconfirmed (regression drill, this round)

The drill above (`Retry-after-post-create/agent failure`) only covers "claim
exists, no `issue_iid`, ticket never attempted" — a workflow that died
*before* `create-gitlab-issue` ran. Re-review of gate 0 found a second,
narrower death window this drill did not cover: `create-gitlab-issue` POSTs
the GitLab issue (success) and only then PATCHes the claim ConfigMap with
`issue_iid`/`issue_url`; if the pod dies, is evicted, or the PATCH call
exhausts its retries in between, the claim is left `state=claimed` with no
`issue_iid` — indistinguishable, from the claim's point of view, from "died
before creating any ticket". A retry would then hit the CAS
claimed-but-unticketed path (`state=claimed-retry`) and call
`create-gitlab-issue` again, which previously blind-created a second ticket
for the same incident.

Fix: `create-gitlab-issue` now searches GitLab for an open issue labeled
`triage-fingerprint-<dedupe_key[0:16]>` before creating anything, and
reuses/appends to it instead of blind-creating. Drill: manually create a
GitLab issue for a synthetic fingerprint (simulating the POST that already
succeeded), pre-create the matching claim ConfigMap in `state=claimed` with
no `issue_iid` (simulating the death before the PATCH-back), then submit the
same incident via `argo submit --from workflowtemplate/red-agentic-triage`
and observe what `create-gitlab-issue` actually does.

**Run 1 — against the WorkflowTemplate before this fix was `kubectl apply`'d
(genuinely reproduced the defect this drill exists to catch):** dedupe key
`drillunconfirm45...`, pod `retry-unconfirmed-drill-v1`. Pre-created ticket
[#495](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/495)
labeled `triage-fingerprint-drillunconfirm45`, pre-created claim
`triage-dedupe-drillunconfirm45...` (`state=claimed`, no `issue_iid`).
Workflow `retry-unconfirmed-drill-tc8s7` ran the CAS claimed-but-unticketed
retry path (`"Claimed-but-unticketed incident retried, no evidence lost"`)
and `create-gitlab-issue` blind-created a **second** ticket,
[#496](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/496)
(`"GitLab issue created: .../496"`) — both #495 and #496 carry the identical
`triage-fingerprint-drillunconfirm45` label, i.e. exactly the two-tickets-
for-one-incident defect this fix targets, live and reproduced. Root cause:
the fixed template was edited in the worktree but had not yet been applied
to the live `red` cluster's `WorkflowTemplate/red-agentic-triage` object —
`kubectl diff` confirmed the running template still lacked the fingerprint
search before this point.

**Fix applied live:** `kubectl apply -f applied-config/03-argo-augmented.yaml`
(`workflowtemplate.argoproj.io/red-agentic-triage configured`; the two
`Sensor` objects in the same file were unchanged, confirmed via `kubectl
diff` first).

**Run 2 — against the patched WorkflowTemplate (proves the fix):** fresh
dedupe key `drillconfirmedv2...`, pod `retry-unconfirmed-drill-v2`.
Pre-created ticket
[#497](https://gitlab.com/davidmarkgardiner/mcp-test-repo/-/work_items/497)
labeled `triage-fingerprint-drillconfirmedv2`, pre-created matching claim
(`state=claimed`, no `issue_iid`). Workflow
`retry-unconfirmed-drill-v2-gzs6v` again hit the claimed-but-unticketed CAS
retry path, then `create-gitlab-issue` logged `"Reused existing GitLab issue
on retry (fingerprint match, no blind-create): .../497"` — no new issue was
created. Confirmed via the GitLab API directly: only one open issue
(#497) carries `triage-fingerprint-drillconfirmedv2`; a note titled "Reused
existing ticket (retry after unconfirmed claim update)" was appended to
#497; and the claim ConfigMap now reads
`{"issue_iid":"497","issue_url":".../497","state":"ticket-created",...}`
(previously empty `issue_iid`).

| Step | Claim | GitLab |
|---|---|---|
| Simulate failure: issue pre-exists, claim `state=claimed`, no `issue_iid` | pre-created manually (same shape as the pre-existing drill) | issue open, labeled `triage-fingerprint-<fp>` |
| Retry submission (patched template) | CAS-guarded retry-claim wins, `state=claimed-retry` -> re-enters `create-gitlab-issue` | fingerprint-label search finds the already-open issue instead of POSTing a new one; note appended, claim PATCHed to `state=ticket-created` with the *existing* `issue_iid` (observed: #497, unchanged) |

```text
GITLAB_TICKET_RETRY_AFTER_UNCONFIRMED_PATCH_NO_DUPLICATE: yes — observed live on `red`
  before-fix repro: workflow retry-unconfirmed-drill-tc8s7, fingerprint drillunconfirm45, tickets #495+#496 (duplicate, defect confirmed)
  after-fix proof:  workflow retry-unconfirmed-drill-v2-gzs6v, fingerprint drillconfirmedv2, ticket #497 (reused, no duplicate)
```
