# Validation on 1 November 2026

## Completed dashboard approval and verified resolution

The human approved MR !2 in the dashboard. The native executor merged the
exact approved head, Flux applied the merge revision, and the application
recovered. Three actual positive/negative admission and HTTP groups passed
over the measured window. A separate completed native verification task
returned a genuine successful tool result. Independent current checks passed,
GitLab confirmed issue #1 closed, and Chrome displayed **Resolved · recovery verified**.

The first readiness wait stopped after 90 seconds, before actual GitOps and
application convergence. The corrected controller separates a read-only
`await_recovery` step from `measure_recovery`. A seven-minute delayed-readiness
regression test remains pending until the app is ready and reserves no
measurement or model call during that wait. The same approved run resumed
through fresh measurement and verification. Its old failed intent is retained.

All 197 runtime tests passed after that correction. The unchanged OTel bundle
had passed 223 tests and its Helm lint/render checks in the preceding phase.
This completed rehearsal includes the earlier operator-assisted commit
correction and the explicit recovery-wait correction. It is not an unattended
first-attempt pass. General Informer ingestion and a literal Pi Harness remain
outside this proof.

## Earlier dashboard approval implementation gate

The current flow replaces direct human GitLab merge with **Approve fix and let
Kagent merge** in the dashboard. The existing open MR and issue are preserved.
The new native executor is Ready. Its runtime rejects merge without a recorded
approval, and the live pre-approval check confirmed that no merge intent or
approval was created. No live approval click or merge was performed during
this implementation.

Offline tests cover the exact-head grant, expiry, changed branches/CI/review,
duplicate clicks, uncertain responses, native task/tool proof, GET-only merge
reconciliation, and the existing physical recovery and verified-closure gates.
The dashboard accepts the configured local operator identity. This is a lab
approval boundary, not workplace SSO proof.

At this earlier checkpoint, native merge, recovery, and issue resolution were
pending human dashboard approval. The earlier operator-assisted commit correction
remains part of this rehearsal's evidence. See the [current flow guide](live/DASHBOARD-FLOW.md).

## Earlier dashboard Start and human GitLab merge flow

The new **Demo** tab was exercised in Chrome against a separate namespace and
target branch. It reached **Waiting for human review and merge**. The real
GitLab issue remains open. No MR was approved or merged by the operator bridge.
The earlier native approval rehearsal below remains separate and untouched.

| Check | Result | Boundary |
| --- | --- | --- |
| Dashboard Start | PASS | An actual browser button accepted one durable run. Repeated starts cannot create another active incident. |
| Fault and observation | PASS | Two repository commits, active faulty policy, zero available application replicas, and three corroborated denials over the real admission window. |
| Classification | PASS | One actual `critical`/`investigate` response at confidence 0.95 admitted dispatch. The threshold remained 0.95. |
| Native investigation and OTel | PASS | Actual specialist task, native skills/resources, Kubernetes and GitLab tools, and received request telemetry. |
| First repair write | REJECTED | GitLab rejected new-branch `start_sha` plus `last_commit_id` with HTTP 400. The unknown original operation and a separate explicit diagnostic rejection are retained. |
| Corrected proposal | OPERATOR-ASSISTED | Source now uses immutable `start_sha` and exact parent/content/diff readback for new branches. An explicitly recorded operator correction created the repair commit. A new actual Kagent task in the original session reconciled that commit and created MR !2. This is not an unattended end-to-end pass. |
| Repository and independent native review | PASS | Exact-head CI passed, and a separate completed read-only native reviewer returned an exact-bound PASS. Static cases do not prove live admission recovery. |
| Human review | WAITING | Chrome shows the real GitLab MR link, passing CI/review, and an open issue. The new specialist has no merge tool or native approval checkpoint. |
| Recovery, native verification, issue closure | NOT RUN | The controller waits for the actual human GitLab merge, then requires Flux, measured admission/HTTP recovery, completed native tool proof, independent current checks, and actual closed-issue readback. |

The same persistent model budget has 28 of 32 attempts reserved and 454,469 of
524,288 input bytes charged at the human gate. No budget was reset. Four
attempts and 69,819 input bytes remain for the post-merge task.

Source review found terminal-state and interrupted-window waits that could
poll forever, plus an incomplete receiver-outage state. Those paths now stop
or remain explicitly passive as appropriate. Duplicate wait events are
coalesced without changing their original timestamps. Browser reloading
preserves the Demo tab. The [flow guide](live/DASHBOARD-FLOW.md) describes the
operator bridge and its limitations.

The Grok design lane hit its reported free-usage limit. The Claude design lane
was cancelled after twenty minutes without a completed result. The native
design, implementation, review, and parent checks do not establish completed
multi-provider review.

## Earlier native approval rehearsal

The connected home-lab rehearsal reached a real native human approval gate.
The classifier admitted the fault, the specialist created the one-field GitLab
MR, its exact-head CI passed, and a separate read-only native reviewer returned
PASS for that repository fix. Merge and post-merge recovery are still pending.
This is not workplace-runtime or completed end-to-end recovery proof.

| Check | Result | Boundary |
| --- | --- | --- |
| Existing OTel suite before changes | PASS, 146 tests | Establishes the preserved local baseline. |
| Updated OTel suite | PASS, 195 tests | Receipt consistency, explicit active-probe policy observations, exact task/span joins, freshness, failed probes, HTTP state, UI behavior, package imports, and Helm mounts. |
| Real Kyverno admission fixture | PASS, 15 checks | Operator-applied healthy/faulty/repaired policies and real HTTP fixture. No agent or GitOps claim. |
| Initial stronger rollout fixture | FAIL, 12 of 13 checks passed | The 20-second test observed old-Pod shutdown before replacement admission. The default 30-second grace period made the intended FailedCreate observation premature. The failed receipt is retained. |
| Corrected real rollout fixture | PASS, 21 checks | A one-second fixture shutdown permits the actual rejected replacement Pod, zero available replicas, repaired policy, current rollout, and successful HTTP reads. |
| Browser fixture in Chrome | PASS | Twelve-stage Recovery view and explicit fixture label. Missing model/MCP/gateway/skill evidence remains unknown. |
| Browser later HTTP 503 | PASS | Recovery changes immediately to blocked. |
| Browser stale capture | PASS | Recovery changes to unknown. |
| Strict public-safety scan of new source/docs | PASS | No private endpoints or credentials in these additions. |

The dedicated kind cluster is `kyverno-agent-poc`, Kubernetes 1.35.0. Kyverno
chart 3.9.2 / app v1.19.2 has admission, background, and report controllers Ready.
The final `registry-demo` Deployment has one desired, updated, ready, and
available replica, with observed generation 2. The invalid-image admission test
remains denied after the policy repair.

The failed local image import encountered a missing multi-platform content
digest. The successful application proof used the cluster's normal image-pull
path. This is not an air-gap or portable image-import proof.

The local fixture script explicitly writes NOT RUN for classifier, native
agent, GitLab, GitOps, and OTel. Those boundaries still apply to that separate
fixture receipt. The connected rehearsal below supplies real evidence for the
later components. Raw receipts and filled configuration remain private.

## Connected native rehearsal

The separate native lab used Kubernetes 1.35, Kyverno 1.17.1, native kagent
1.0.0-alpha17, and Substrate 0.6.0-alpha3. This lane uses the native Go ADK
Harness with Substrate and the scoped SQLite workflow ledger. It does not
establish that a Pi process was embedded in that Harness.

| Check | Result | Evidence boundary |
| --- | --- | --- |
| Healthy GitLab/Flux baseline | PASS | Real private demo repository, successful CI, exact source/applied revision, current Deployment and actual positive/negative admission probes. |
| Repository fault and blocked rollout | PASS | Two real Git commits apply the registry typo before starting the Recreate rollout; known-good Pod dry-runs and current ReplicaSet FailedCreate events fail under the named rule. |
| Critical classifier gate | PASS | First independent window was suppressed at confidence 0.93. The next exhausted its answer cap and stayed unknown. A later independent window was admitted at 0.97 with the threshold unchanged at 0.95. Three classifier reservations remain spent. |
| Native specialist | PASS to approval gate | Actual task loaded both native skills and knowledge files, read both MCP backends, diagnosed the current typo, proposed the one-field fix and requested native tool approval. |
| Exact-head repository checks | PASS | Head `05c642fcf680ea5af8558dbc58d85534c0582498`; successful `policy-tests` job and four named JUnit contract cases. These are static checks, not Kyverno admission. |
| Independent native review | PASS for repository fix | Separate completed read-only reviewer task matched the exact binding, CI and diff. It explicitly left live recovery pending. |
| Native human approval | WAITING | Actual INPUT_REQUIRED approval and tool-call identities are recorded separately from the independent reviewer. No human decision or merge was supplied. |
| Received OTel | PASS for investigation | Actual native model, skill/resource loads, Kubernetes MCP, GitLab MCP and model-gateway spans join the investigation task. Sixty-two received metadata logs and 173 received spans are retained without changing their timestamps. Final verification telemetry remains absent. |
| Post-merge Flux and application recovery | NOT RUN | Requires actual human approval, merged revision, live policy/probe/rollout/HTTP evidence and a terminal native verification receipt. The demo application remains blocked at the deliberate fault. |

The shared worker advertised an obsolete Pod address. A dedicated worker pool
and Harness were created for this rehearsal; their advertised and current Pod
addresses matched. No shared worker restart or registration repair was used.

The first native adapter delivery used an older HTTP route that returned an
empty HTTP 200 without entering the native gateway. Source, Agent Card and
exact-session task-list reads proved nonacceptance. Its source, empty response,
outbox and message identity were preserved. An explicitly journalled operator
correction rechecked the current fault and delivered that original identity to
the advertised `/agents/` route. This does not prove automatic redelivery or
exactly-once execution for unknown outcomes.

The first provider canary rejected temperature zero. It remains a spent model
attempt. Temperature one and low reasoning effort were configured for the same
model; response limits, the confidence gate and total durable budgets were
preserved. The policy API omits native observedGeneration, so that field remains
null and the explicit stable-read/admission-probe proof variant is used.

General application log/event ingestion, deployment-time agent injection, the
literal Pi-Harness integration, and the meaning and application contract of
Informer remain separate work. The current collector is deliberately scoped to
this synthetic registry-policy incident.

## Dashboard approval and live-flow iteration

The separate dashboard rehearsal completed the human approval, native guarded
merge, GitOps/application recovery, native verification and verified issue-close
path. Its dashboard was observed showing **Resolved · recovery verified**. This
was an operator-assisted rehearsal: a repository commit correction and recovery
wait correction were required. It is not an unattended first-attempt pass and
does not change the earlier native-approval lane described above.

A subsequent user-started incident stopped at fault observation before any
classifier or native task. The first measurement included a historical denial
while the previous healthy rollout was still available. Admission correctly
rejected that packet, leaving only two accepted denials within the measured
window. The source now waits for the exact rollout revision and an accepted
denial before starting its three-probe window. The original stopped incident and
failed receipts remain preserved; the upgrade does not retry it automatically.

The visual iteration embeds the real OTel map and nine-stage rail directly in
Demo, with automatic current-task following, a current-operation explanation and
bounded received-event feed. Desktop and phone-width browser inspection confirmed
the layout and blocked-state guidance. Offline tests cover task/run correlation,
causal span selection, first snapshot, stale/future/duplicate/replay handling,
legacy viewer arrival timestamps, exact dashboard approval and verified closure.

A fresh read-only budget preflight exported one real coordinator span and two
logs through the deployed shared collector. All three records were read back,
with zero export failures. The diagnostic trace was correctly excluded from the
active incident. This proves the new coordinator transport against that receiver;
it does not prove a fresh native fault-to-resolution run with the new UI.

That final live rerun remains pending a separately authorized model allowance.
The existing allowance has zero requests remaining out of 32. It has not been
reset or raised. The current incident remains blocked and its issue stays open.
General Informer ingestion and deployment-time agent embedding remain unverified.

The stopped-incident follow-up adds an explicit, idempotent Resume action for a
pre-classifier fault-observation failure. A separate `recheck_fault` operation
preserves the old intent and physical receipts, measures its own fresh window and
validates its exact Admission candidate. Original native approval and closure
gates remain unchanged. A trusted allowance can be bound to this one incident;
remaining calls cannot start a second demo. Definitive UI rejections permit a
later manual request after readback, while accepted or uncertain outcomes stay
held without automatic retries.

Validation passed 254 runtime tests and 239 dashboard/OTel tests, plus Helm
checks. Browser readback confirmed the new stopped-state explanation, Resume
control and exact exhausted-allowance reason. A real zero-budget Resume POST
returned HTTP 409 without creating a resume reservation, changing the original
run/intent/call/event rows, or modifying any of its twelve physical receipt files.
Successful resume remains offline-proven only until the new allowance is
authorized. The proposed separate proxy/PVC/ModelConfig passed server dry-run;
it has not been activated and no extra model request has been made.

## Authorized continuation to the reviewed PR

The operator subsequently authorized the separate sixteen-call allowance for the
same incident. The fresh window supplied three actual denials over 65 seconds.
Its first classifier decision was critical/investigate at 0.93 and was suppressed.
One explicitly recorded follow-up used a new physical window and candidate; the
actual model returned 0.97 and the unchanged gate admitted a native investigation.

The native investigator diagnosed the exact registry typo but GitLab returned
HTTP 401 before proposal creation. The existing OAuth credential had expired.
Its provider-managed refresh retained the same account/project, and the existing
runtime Secret was updated. A read from the actual runtime then succeeded. One
journaled same-session native continuation created the minimal one-field MR.
Its exact-head policy-tests job and two required JUnit cases passed. A separate
completed native reviewer returned the exact-binding PASS. This is an
operator-assisted rehearsal, not an unattended first-attempt result.

The human approved the exact reviewed commit in the dashboard. The operator
authorized a separate four-call finisher for native merge and verification.
The original ledgers remained unchanged, with two of the sixteen calls still
available. Only the executor template moved to the new allowance. Its completed
native task merged the approved MR, corroborated by GitLab readback.

Flux then exposed a second expired credential in its separate source Secret.
After the same-account credential refresh and authenticated Git-fetch proof,
the source fetched the exact merge revision and restored the healthy policy.
The application remained on Kubernetes' pod-creation failure backoff, then
recovered on its natural retry. No application restart or manual replacement pod
was used to bypass that wait. The same deployment reached one ready replica,
and Flux reported the exact merge revision applied and healthy. Three real
valid-admission, invalid-denial and expected HTTP groups passed over the required
stable recovery window. A separate completed native verification task and
independent current runtime checks passed before the issue was closed. GitLab
readback confirmed both the merged MR and closed issue; the controller reached
`closed` with `closedVerified: true`. All four finishing calls were consumed,
without resetting or changing the earlier ledgers.

Actual native/model/gateway/skills and MCP records were observed in the dashboard.
The older receiver strips run IDs from coordinator records, so these records
join the current run through its actual persisted caller trace/span/start identity
and recorded operation intent. Raw received attributes and timestamps remain
unchanged. Some MCP transport parents are not exported; their server records
join only a unique native tool call in the same trace with the exact tool,
fixed backend service and strictly enclosing interval. This inference is labelled
explicitly and has no authority to pass a workflow or recovery gate.

## Fresh dashboard-controlled rehearsal

A subsequent fresh incident completed the full flow on 2026-11-01. Preflight
verified the managed GitLab account, a typed repository read from the actual
runtime, Flux Git-fetch authentication, the exact healthy policy and one ready
application replica. Two completed-run model proxy workloads were stopped to
release lab capacity; their persistent ledgers were retained unchanged.

The actual classifier returned critical/investigate at 0.95 on its first request,
meeting the unchanged 0.95 gate. Native triage created a new repair MR. Exact-head
CI and independent native review passed. The human approved the exact head in
the dashboard, and a separate native executor task merged it. No credential
repair, classifier follow-up or triage continuation was needed after Start.

Flux fetched the approved merge revision. Kubernetes' failed-create backoff
delayed the application; the natural retry created its Pod at 18:28:55 UTC and
the Deployment became available at 18:28:56. No manual application restart was
used. The measured recovery window passed, separate native verification completed
and independent runtime checks passed. GitLab issue closure was read back, and
the controller reached `closed` with `closedVerified: true` at 18:31:04 UTC.
Fourteen of sixteen model request reservations were consumed.

This is an operator-prepared, human-approved isolated lab rehearsal. It is not
office deployment validation. The connected lab used Kagent `1.0.0-alpha17`,
Substrate `v0.6.0-alpha3`, Kyverno `v1.17.1`, Flux source `v1.6.2` and Flux
Kustomize `v1.6.1`. The stage projection's global 160-observation cap evicted
early-stage OTel during later work. Controller descriptions and histories remained
available. Full per-stage component retention remains unimplemented.

## Numbered stage inspection

The nine stage controls now open a read-only detail panel with stage purpose,
recorded outcome and fields, controller history, stage-local observed components
and available trace links. The backend uses its existing canonical step map to
project history, including fault rechecks and investigation continuations.
Missing retained OTel remains explicit; controller receipts do not establish
native component execution. Selection persists through polls and resets on a new
run. Stable control and evidence nodes preserve keyboard focus during updates.

Validation passed 297 runtime tests and 245 dashboard/OTel tests, plus JavaScript
syntax and Helm checks. Browser checks on the existing resolved incident clicked
all nine numbers and confirmed their matching panels, then selected verification
using the keyboard. The public workflow payload was identical before and after
this viewer-only change. No new incident, approval or native task was sent.

## Office handoff source validation

The office handoff adds sanitized settings, runtime and budget resources,
read-only RBAC, Flux resources, GitOps fixtures, CI, an image recipe and an
implementing-agent task. The maintained packager includes these files and routes
its start page to `OFFICE-HANDOFF.md`.

Portability fixes derive the allowed dashboard GitLab origin from trusted
operator configuration and propagate the configured native HTTP origin and user
partition to initial dispatch as well as CLI and gRPC calls. Unrelated link
origins remain blocked. These configuration paths have offline coverage; they
have not been validated against an office runtime.

The full source check exposed an existing race between an initial operator
recovery readback and its eligibility snapshot. Three deterministic regressions
failed before the fix for fault resume, classifier follow-up and triage
continuation. The fix reads back a concurrently reserved operation before
returning an eligibility conflict. It does not create another operation or
relax the admission, budget or task-identity gates.

A clean archive extraction passed 304 runtime tests, 17 budget-proxy tests,
246 OTel/dashboard tests and four packaging/resource/CI checks. Packaging checks
verify checksums, imports and repackaging without this checkout, and import the
runtime image's copied modules in isolation. Static CI accepts the healthy
policy contract and rejects the faulty pattern. JavaScript syntax, Helm lint
and example render checks passed. Gitleaks and detect-secrets reported no
findings. Public-safety pattern matches for existing semantic versions and one
timing value were individually reviewed as false positives.

The archive contains source and placeholder examples. It contains no approved
office image, native CLI binaries, filled private profiles, tokens or private
task receipts. Image building, native API/SSO/MCP authorization binding and the
office acceptance run remain explicit target requirements in the handoff.

Run the maintained source verifier with:

```sh
python3 -B work-agent-bundles/otel-agent-flow/scripts/verify-bundle.py
```

Run the real policy/rollout fixture using the isolated-context command in
[README.md](README.md). The script requires a fresh namespace and output receipt.
It restores the healthy policy and leaves the application for inspection.

The design follows Model the Domain for the incident/receipt state reducer,
Boundary Discipline for strict external snapshot parsing, and Prove It Works
for actual admission/HTTP probes and browser-observed failure states. Independent
cross-provider review was unavailable due to confirmed external model usage
limits. The native implementation candidate and parent verification do not
establish a multi-provider review.
