# Fixed-scope connected runtime

For dashboard Start, native triage, dashboard human approval, native executor
merge, verification and issue closure, use
[Run the dashboard-controlled recovery demonstration](DASHBOARD-FLOW.md).
Start an office adaptation with [the office handoff](../OFFICE-HANDOFF.md).
The loopback operator bridge uses Python 3.10+ and holds operator credentials
outside the runtime MCP service. The legacy native merge tool below remains
available for earlier rehearsals but is not bound to the dashboard specialist.

Stdlib Python 3.9+; no dependency install, subprocess, arbitrary SQL tool,
Kubernetes write, model invocation or watcher. Tests use explicit fakes and
establish only offline behavior. Parent owns infrastructure, native agents,
CI, skills, probe privileges, approved model-route allowances and human decisions.

## Start and configuration

```sh
python3 /app/runtime.py --config /config/config.json --data /data --port 8080
```

Mount actual verified config (schema in `config.example.json`), persistent
`/data`, three distinct random `/config/investigator.token`,
`/config/reviewer.token`, `/config/operator.token` files, and a GitLab token file.
`GITLAB_TOKEN_FILE` optionally overrides the default `/gitlab/gitlab.token`
**path**, never a token value. Standard Kubernetes SA token/CA mounts are used.
One replica owns this run's WAL/FULL SQLite ledger. Its canonical config hash
is immutable; never clear it to restore budgets or retry an uncertain action.

The read-only viewer can retain already-received primary-task metadata from
`/data/observed-traces.json`, mounted read-only. Its exact envelope is
`{schemaVersion:1, source:"received-otel-dashboard", capturedAt, traces, logs?}`.
The trusted operator copies actual dashboard trace/log projections; fixtures,
raw OTLP, raw message bodies and reconstructed missing fields are not accepted.
The complete file is at most 1 MiB, with 1..4 traces, at most 512 spans per trace
and 256 optional logs. Every trace must match the independent
`/profile/profile.json` native agent and primary task; reviewer traces require a
separate future binding and are currently excluded. Logs require an accepted
trace/span, exact metadata shape and the receiver's sanitized message format.

The viewer preserves all original IDs, times, receivedAt, status, usage,
attributes and references. Live copies win on traceId/log ID; archive copies
carry `retainedSource:"operator-received-archive"`. It never restamps, creates
spans, re-exports OTLP or writes state. Historical retention does not refresh
policy/probe health or establish native task completion. Log trace/service
filters still apply. With archived logs, `retained`/`matching` count the known
merged current-response/archive list (`countScope` names that scope); original
upstream totals remain `upstreamRetained`/`upstreamMatching`. Missing or invalid
archives leave the original live response unchanged. Offline archive checks:
`python3 -B -m unittest -v test_viewer.py`.

Hashes: `core.digest(document)` and `core.digest(document['spec'])` use sorted,
compact JSON. Full-file hashes pin repository documents; spec hashes pin actual
live specs. Verify API defaulting and represent it explicitly in the reviewed
file. The healthy document must equal the faulty one with only the permitted
image pattern changed. Expected HTTP body hash uses exact bytes (the fixture is
`hashlib.sha256(b'recovered\n').hexdigest()`). CI must publish actual JUnit cases
and successful job names matching config. Missing test metadata is unverified.

## HTTP and tools

- GET `/healthz`: public process health; no cluster/readiness claim.
- GET `/state` and POST `/control`: operator Bearer token only.
- POST `/mcp/investigator`: investigator Bearer token, six fixed tools.
- POST `/mcp/reviewer`: reviewer Bearer token; read/inspect only.

Tools: `read_kyverno_incident()`, `read_policy_repository()`,
`propose_policy_fix(reason, image_pattern)`, `inspect_policy_fix()`,
`merge_policy_fix()`, `verify_recovery()`. Only proposal accepts arguments;
pattern must be exactly `docker.io/library/*`. All paths/identities are fixed by
config. Reviewer cannot propose, merge or publish its own independent verdict.
Parent's native investigator MCP binding **must** configure `requireApproval`
for `merge_policy_fix`. Operator token is never an agent tool credential.

Incoming traceparent is preserved. Tool-call metadata accepts `_meta` keys
`tool_call_id`, `toolCallId`, `mcp.tool.call.id` or `X-Mcp-Tool-Call-Id` header;
task metadata accepts `task_id`, `taskId`, `a2a.task.id` or `X-Kagent-Task-Id`.
These correlate actual MCP SERVER spans (`kind=2`), never authorize actions.
OTLP traces/logs are metadata only. Missing context creates a new trace without
inventing a native parent/task. Export failure stays visible in the ledger.
MCP envelopes <=8 KiB, inbound <=64 KiB, bounded upstreams, no redirects.

## Admission class

Import `Admission(config, '/data/kyverno.sqlite')` or pass the shared `Ledger`.
Only the trusted collector calls it; JSON consistency is not authentication.
`observe(packet)` takes this exact field structure (names below denote actual
values; never copy test fake observations into live evidence):

```text
{schema_version:1, cluster_id, namespace, application, policy_name, rule_name,
 cause:"known_good_admission_policy_regression",
 probe:{probe_id, observed_at, kind:"valid", result:"denied",
        image:"docker.io/library/busybox:1.36"},
 policy:{uid, generation, observed_generation, policy_spec_sha256,
         policy_revision, image_pattern:"docker.io/libary/*"},
 denial:{source:"kubernetes-dry-run", policy_name, rule_name},
 rollout:{uid, generation, observed_generation, desired_replicas:1,
          updated_replicas:0, available_replicas:0, failed_create:true,
          event_id, policy_name, rule_name}}
```

Three distinct fresh probes spanning 60..120s, same faulty policy UID/gen/hash/
revision and blocked rollout generation create a candidate. Replays do not
count; reused IDs with changed evidence reject. Invalid-image enforcement,
generic errors, wrong scope and stale/uncorroborated evidence are suppressed
with counters. Fingerprint excludes pod names, timestamps and Git revisions.

Absent native policy `observed_generation` is null and requires explicit
`observation_method:"stable-read-and-admission-probes"`, `policy_read_before`,
`policy_read_after` inside `policy`. Each read is exactly:

```text
{uid, generation, policy_spec_sha256, ready:true, deleting:false,
 enforcement:"Enforce", observed_at: unix seconds}
```

Actual matching policy reads must bracket the dry-run observation. This never
fills in a missing native status field.

`classify(candidate_id, callback)` irreversibly reserves one of twelve requests
before `callback(untrusted_candidate, limits)`. No default/fallback exists.
Approved route must enforce supplied ceilings (16KiB input, 16,384 input tokens,
512 output tokens); reserved total ceilings remain visible across restarts.
Return the actual response adapted to:

```text
{request_id, model, usage:{input_tokens, output_tokens},
 result:{choice:"investigate"|"ignore"|"unverified",
         severity:"critical"|"high"|"medium"|"low"|"unknown",
         confidence:0..1, cause:"known_good_admission_policy_regression",
         evidence_ids: exact candidate IDs}}
```

Only investigate/critical/confidence>=.95 admits. Confidence is not a calibrated
guarantee. Outage/malformed response consumes the reservation and stays unknown.
A repeated candidate never calls again; a fresh window can use remaining
allowance. Stale evidence cannot classify or dispatch.

`dispatch(callback)` persists one message identity before calling
`callback(dispatch_packet)`. Return actual `{message_id, task_id, task_state}`
with SUBMITTED/WORKING/INPUT_REQUIRED/COMPLETED state. Timeout/crash stays unknown.
Read back the original message using the native API, then call
`reconcile_dispatch(actual_receipt)`. Never send a fresh message to resolve an
unknown outcome. One outbox/admission per run; no exactly-once claim.

## Operator actions

Copy `binding` exactly from inspect (project_id, iid, head_sha, base_sha,
base_file_sha, incident_id, run_id). Digests below refer to retained **actual**
native/operator response artifacts, not manufactured receipts. All timestamps
are actual Unix seconds. Control actions return small acknowledgements.

- `record_review`: action, binding, reviewer_id (configured), task_id (distinct
  native reviewer task), task_state:"COMPLETED", verdict:"PASS",
  native_receipt_sha256, reviewed_at, valid_admission:"pass",
  invalid_admission:"pass". Re-reads diff/CI/JUnit at exact current head.
- `record_native_approval_request`: action, binding, task_id (admitted native
  specialist), approval_id, tool_call_id, tool_name:"merge_policy_fix",
  task_state:"INPUT_REQUIRED", native_receipt_sha256, observed_at.
- `authorize_merge`: action, binding, matching task_id/approval_id/tool_call_id/
  tool_name, decision:"approved"|"denied", principal_type:"human", principal_id
  (configured), native_receipt_sha256 (actual distinct decision artifact),
  decided_at. Expires after 900s. Generic approved:true rejects. If native API
  cannot establish the actual human principal/tool-call binding, stop at
  INPUT_REQUIRED; do not fabricate missing fields.
- `record_probe_receipt`: `{action,receipt}`. Receipt fields: receipt_id, run_id,
  incident_id, source:"operator-kubernetes-dry-run", source_receipt_sha256,
  merge_sha, policy_uid, generation, observed_generation, policy_spec_sha256,
  observations. Each observation: probe_id, observed_at, kind:valid|invalid,
  result:admitted|denied|error, policy_name, rule_name.

For absent native observed generation, probe receipt uses null and adds
`observation_method:"stable-read-and-admission-probes"`, `policy_read_before`,
`policy_read_after` with the same read format above. All actual probes lie
inside this stable read bracket. Invalid denial must actually name this
policy/rule; the privileged probe runner retains raw responses and attests
their extracted identities. An unrelated generic denial is insufficient.

Recovery joins post-merge valid admissions (>=3), invalid denial, stable healthy
policy, Ready/nondeleting Enforce, exact Flux source/applied merge revision,
current Deployment rollout and three actual expected HTTP hashes. It preserves
native observed_generation:null and exposes policy_observation_method,
active_probe_generation and actual read metadata for the alternative proof.
Parent still needs a terminal native verification task and real retained
model/skill/gateway telemetry before calling the connected demonstration done.

## Operator projections and native delivery

`collect_probe.py` runs with the separate operator kubeconfig and creates only
fixed Pod dry-runs. Collect three distinct denials across 60 to 120 seconds,
then pass their actual packets to `Admission.observe`. Do not put this
operator credential or Pod-create permission in the agent runtime.

Use [the direct classifier](CLASSIFIER.md) and
[one-shot native dispatch](NATIVE-DISPATCH.md) against the existing ledger.
The native 1.x JSON-RPC route is `/agents/{namespace}/{agent}/`; the older
`/api/a2a/` route returned an empty HTTP 200 in this lab. Discover the advertised
Agent Card before delivery. An empty transport response establishes no task.
The rehearsal retained the incorrect-route attempt and proved that its handler
never accepted input before an operator corrected delivery with the original
message and Session identities. This was an explicit operator reconciliation,
not automatic redelivery of an uncertain input.

`pending_view.build` maps actual accepted-task, candidate, proposal, CI and
independent-review receipts into the existing recovery schema up to the human
gate. It requires the actual native task creation timestamp and current
INPUT_REQUIRED state; it supplies no human approval or recovery receipt.
The trusted operator writes its profile and snapshot separately to the passive
viewer. CI receipt admission labels describe the named static policy-contract
fixtures. The later admission-recovery stage still requires actual Kubernetes
probes.

`viewer.py` reads the existing OTel dashboard and strict recovery files. It
contains no invocation or approval endpoint and receives no credentials. Its
separate pre-admission projection can show scoped classifier status while the
native task is unverified; that projection can never report recovery.

## Offline validation and limits

```sh
python3 -m unittest -v test_runtime.py
python3 -m py_compile core.py admission.py runtime.py
```

Tests use fakes and local HTTP servers; no live cluster/model/GitLab proof.
The source SHA has a GitLab merge precondition. Target SHA has a pre-merge read;
protect the isolated branch from concurrent writers. Uncertain writes reconcile
their fixed identities without automatic retry. No HA/host-loss claim.
