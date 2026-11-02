# Run the dashboard-controlled recovery demonstration

The **Demo** tab starts one real incident in a preconfigured lab namespace and
GitLab branch. The human approves the reviewed repair in the dashboard.
Kagent merges that exact commit, waits for GitOps and live application recovery,
and verifies recovery before the controller resolves the issue. The dashboard
does not call GitLab's merge API directly. There is no second approval checkpoint.

## Prepare the fixed lab

Provision the runtime, Flux source and Kustomization, application, policy,
specialist, and independent reviewer before starting the bridge. Include
`gitlab_lifecycle.py` in the runtime source mount. Keep the runtime Kubernetes
service account read-only. Operator credentials for dry-run probes and scoped
configuration changes stay outside the agent tools.

Bind the specialist to read incident/repository and propose/inspect policy fix
tools. Instruct it to finish triage after proposing the MR and checking CI.
Bind the reviewer to read-only tools. Both load the pinned Kyverno knowledge.
Use a small native executor Agent with only `merge_dashboard_approved_fix` and
`verify_recovery`. Its separate merge and verification requests each call one
tool once. Enable its runtime with repeated `--dashboard-human-id` arguments
for the trusted local approvers. The merge tool is disabled by default and
independently requires the recorded exact-head approval. Native tools cannot
record approval. The legacy `merge_policy_fix` retains its separate old protocol.

Create private settings with these fields. Never add filled settings to the
public bundle.

| Field | Value |
| --- | --- |
| `ssh_argv_file` | Private JSON array containing the fixed SSH prefix. |
| `gitlab_token_file` | Private file containing the current OAuth or personal access token. The adapter sends Bearer authorization. |
| `base_config_file` | Valid `core.Config` for the isolated target. |
| `project_id`, `namespace`, `target_branch` | Exact fixed scope matching that configuration. |
| `kubeconfig` | Operator kubeconfig path on the remote executor. |
| `native_cli`, `grpcurl`, `proto_dir`, `native_address` | Verified native CLI, gRPC client, proto directory, and loopback controller endpoint. |
| `native_controller_origin`, `native_user` | Trusted controller HTTP origin reachable from the runtime Pod and the verified native user partition. The same user applies to CLI, HTTP dispatch and gRPC readback. These lab transport conventions do not establish workplace authentication. |
| `specialist_agent`, `reviewer_agent` | Existing native Agent names matching the configuration. |
| `human_merger_ids` | Nonempty integer array of trusted dashboard human IDs. This existing settings key also supports the earlier direct-human-merge rehearsal. |
| `dashboard_principal_id` | Trusted current dashboard human ID in that array. The browser cannot select an identity. |
| `executor_agent` | Native Agent for the guarded merge and later verification requests. |
| `runtime_deployment` | Existing runtime Deployment name. Default `kyverno-runtime`. |
| `collector_dir` | Remote directory containing `core.py`, `runtime.py`, and `collect_probe.py`. |
| `faulty_policy_file` | Private reviewed faulty policy fixture with the configured digest. |
| `application_file` | Repository application path. Default `deploy/application.json`. |

Use the existing model-budget proxy and persistent budget database. New demo
run IDs do not create or replenish model allowances. Confirm that the healthy
application is available and Flux has reconciled its exact source revision.

## Start the bridge

Keep the existing read-only OTel receiver accessible on loopback port 8792.
From the repository root, run the following command after replacing the two
private paths.

```sh
python3 work-agent-bundles/kyverno-application-specialist/live/flow_server.py \
  --settings '{{PRIVATE_SETTINGS_PATH}}' \
  --data '{{PRIVATE_CONTROLLER_DIRECTORY}}' \
  --assets work-agent-bundles/otel-agent-flow/ui
```

Open `http://127.0.0.1:8791/#demo` and click **Start demonstration**. Keep the
Mac and SSH tunnel running through approval and recovery. The bridge binds loopback
only and checks Host, Origin, a per-process CSRF token, and the request UUID.
Browser requests cannot choose a namespace, model, branch, command, or token.

## Follow the actual incident

1. Prepare the run-specific runtime ledger and create the real GitLab issue.
2. Commit the faulty policy, wait for its actual application, then commit the rollout trigger.
3. Collect three corroborated denials over 60 through 120 seconds.
4. Ask the classification model once. Only `critical`, `investigate`, and confidence at least 0.95 permit dispatch.
5. Dispatch one native Kagent task. Follow its real MR, exact-head CI, and independent native review.
6. Inspect the MR link, exact commit, CI, and independent review. Click **Approve fix and let Kagent merge** in the dashboard.
7. Wait for the native executor's guarded merge. Approval expires within 15 minutes until its merge intent is reserved. A changed head, branch, CI, review, or issue blocks the merge.
8. Wait for actual Flux and application readiness. The read-only wait does not assume a 90-second completion time. Only then collect three valid-admission, invalid-admission, and HTTP groups over 60 through 120 seconds.
9. Run a separate native verification task. Resolve the issue only after its completed tool result and independent current runtime checks agree.

Approval uses a CSRF-protected `POST /api/demo/approve` carrying only the request
UUID, run ID, and displayed head SHA. The bridge records one canonical approval
per run before waking the worker. Repeated clicks coalesce. A lost reply causes
read-back of the original grant, without another approval or merge send.

The loopback origin and configured operator ID identify the lab approval
boundary. They do not establish workplace SSO identity. GitLab's actual merge
actor is recorded separately from the approving human.

The Demo tab keeps a nine-stage process rail, the OTel component map, the
current operation and next gate, and the latest twelve received records in one
view. It follows the current incident automatically. Inspecting a trace pauses
following; **Follow live** returns to the incident. Longer evidence and controller
history stay under disclosure controls.

The rail outline represents durable workflow state. Purple activity requires a
newly received, recent OTel record. The first snapshot, old records, duplicate
delivery, future timestamps and unrelated incidents do not pulse. Recorded
replay is labelled separately. A completed span cannot pass a workflow stage.
Investigation, review, merge and verification join exact native task identities
and available session identities to retained, causally connected spans. A missing
trace remains unavailable. Merge, CI success, agent text and elapsed time cannot
turn the ticket green.

The coordinator exports metadata for operations its own code executes, including
fault injection, classification, observation waits and recovery. These records
are labelled **Coordinator reported** and highlight only its caller node. Native
model, skills, gateway and MCP activity requires the corresponding received
execution evidence. Skill and resource reads share a Skills and knowledge node;
redacted arguments cannot establish which knowledge package was loaded.

Set `controller_otlp_endpoint` in the private bridge settings to the trusted OTLP
HTTP collector origin. A local collector tunnel can use
`http://127.0.0.1:8793`. Export uses a bounded asynchronous queue; failure does not
repeat the underlying operation. No browser OTLP write endpoint is exposed. An
older receiver can retain the explicit `flow.workflow` and `flow.result` aliases.
For legacy logs without collector receipt time, the bridge separately records
`viewerReceivedAt` and labels freshness as observed by the viewer. It preserves
event timestamps and never invents a collector receipt time.

The runtime journals its exact-SHA merge intent before one GitLab PUT. A
completed native task with an uncertain tool result continues GET-only
observation of that original intent. It does not resend the PUT. Recovery
starts only after the actual approved merge is corroborated.

New repair branches use immutable `start_sha`, an exact healthy content digest,
and read-back checks for the commit parent and permitted diff. The optional
`last_commit_id` action check is omitted for that new-branch operation. The
rehearsal observed GitLab reject that combination against the nondefault source
branch. GitLab's [file-change check](https://gitlab.com/gitlab-org/gitlab/-/blob/master/app/services/files/base_service.rb)
uses `start_branch` for this validation. Existing-branch fault commits retain
their file concurrency check.

## Preserve unresolved runs

Repeated clicks attach to the current run. Restarting a known observation wait
continues polling. An interrupted write or model send stops as unknown and
retains its original intent. Reconcile the original operation before any
explicit continuation. Never clear a ledger, invent a receipt, lower the
classifier threshold, or reset the budget to make the demonstration pass.

Start and preparation check the existing model allowance before creating an
issue or injecting a fault. A new run ID does not replenish it. Fault measurement
waits for an Admission-accepted denial at the exact rollout commit. A historical
FailedCreate event or still-healthy old rollout cannot consume the first probe.
Readiness observations remain separate from the three measured probes. Existing
failed windows retain their original receipts and remain stopped after upgrade.

For a stopped fault-observation window, **Resume incident** continues the same
incident after an explicit operator request and a verified available model
allowance. It creates one separate `recheck_fault` operation. The original
observation intent, failed window, issue, fault commits and rollout remain intact.
The new operation collects its own three fresh denials over the unchanged
60-through-120-second window before classification. It cannot repeat issue
creation, fault injection, a classifier call or a native task. Interrupted rechecks
only read their own retained receipts; they do not start another window.

Resume uses `POST /api/demo/resume` with exactly the canonical request UUID and
current run ID under the same Host, Origin and CSRF checks. Accepted duplicate
requests return the original recovery operation even if its allowance has since
been consumed. A new request fails closed when the existing allowance is
exhausted or unavailable. The UI distinguishes a stopped incident from a running
incident and shows the actual budget reason. Start remains unavailable until the
current incident has verified closure.

The private adapter settings can optionally select a trusted `model_origin` for
a separately authorized allowance. This is an operator setting, never a browser
field. It must pass the classifier's origin validation and is used consistently
for classifier requests and budget-health reads. Allocating another allowance is
separate from resuming; Resume cannot reset, raise or replace a budget ledger.
Set `model_allowance_run_id` to bind a separate allowance to that exact incident.
A bound allowance rejects another run's preparation and disables Start even if
calls remain after resolution. It cannot fund a second demo implicitly.

The trusted operator API also supports one `request_classification_followup`
after a valid first critical/investigate decision falls below the unchanged 0.95
gate. This is a new three-probe physical window and a new actual candidate, not
a resend of the suppressed candidate. Another suppression stops. There is no
browser endpoint for this operator decision.

After a completed investigation stops before creating a proposal, a trusted
operator can call `request_triage_continuation` once. It verifies the original
completed task/session, absent proposal, restored typed repository access and
the incident's available allowance before reserving one new native message in
that session. The native agent continues the unfinished repository stage; its
original diagnosis, task and failure receipts remain recorded. Exact prior and
current task identities remain available to the OTel projection.

Check GitLab credential validity before paid investigation. This lab uses an
operator-managed OAuth credential with an expiry; the runtime reads its existing
mounted Secret on every request but does not refresh OAuth credentials itself.
After routine credential refresh, verify the same account/project and a typed
repository read from the actual runtime before continuation. A credential repair
does not authorize a new project or a broader tool grant.

Check the Flux source credential separately: it can use a different Secret from
the native tools. A successful GitLab API call does not prove Git fetch access.
After an authorized refresh, verify the same repository and branch, then read
back the source artifact revision. Keep recovery pending until Flux applies the
exact merge revision and the application is ready. A long fault can leave the
ReplicaSet backing off pod creation even after the policy has recovered; report
that wait without claiming readiness or silently restarting the application.

New native merge and verification operations check remaining execution capacity
before reserving any intent, call or telemetry context. Merge requires four
calls available for merge plus verification; verification requires two. A short
or unverified allowance produces a pending workflow receipt and GET-only budget
checks. An already accepted native operation continues its original readback
even if the allowance later reaches zero. No allowance is raised or reset.

An operator-assisted rehearsal continuation retains its original task, send,
and commit receipts. A private `operator-triage-continuation.json` may bind a
separately observed follow-up task to the original task and session. The bridge
does not create that file or send a follow-up automatically. Record the
intervention in the incident timeline and qualify the rehearsal accordingly.

Each numbered stage is an inspectable summary. Select numbers 1 through 9 to
see its purpose, latest controller outcome, recorded fields and stage-specific
components observed in retained OTel. Controller history uses the projector's
canonical step mapping, including explicit fault rechecks and native
continuations. It remains available when old telemetry is no longer retained;
it does not establish native component execution. Trace links require the exact
observed span to remain available. Selection stays pinned during updates;
Follow current stage returns to the live stage. Stage inspection issues no
workflow command and cannot approve, resume or start an incident.

The loopback bridge is a bounded lab operator, not deployment-time injection
or a production controller. General logs/events ingestion, Informer integration,
and a literal Pi runtime inside Kagent remain separate work.
