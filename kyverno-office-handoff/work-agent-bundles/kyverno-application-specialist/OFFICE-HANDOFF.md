# Reproduce the dashboard recovery demonstration in an office sandbox

Give the work agent the complete extracted archive. Start with this file, then
[the dashboard procedure](live/DASHBOARD-FLOW.md). Keep the existing office
GitLab, Flux, Kagent, gateway, authentication and OTel delivery paths.
Use [the work-agent task](office/WORK-AGENT-PROMPT.md) as the implementing prompt.

The source and examples are ready for environment binding. Office deployment
and acceptance are still required. No office cluster was changed by this handoff.

## Reproduce this flow

1. Click **Start demonstration** in the dashboard.
2. Create one issue and inject the isolated policy typo through GitLab and Flux.
3. Collect three actual denials over 60 through 120 seconds.
4. Classify once. Require `critical`, `investigate` and confidence at least 0.95.
5. Let the specialist investigate, propose the one-field fix and finish its task.
6. Require CI and an independent native review of the exact proposed head.
7. Approve that head in the dashboard. The native executor performs the merge.
8. Wait for the exact Flux revision and application readiness, then measure
   three valid-admission, invalid-denial and expected HTTP groups over 60 through
   120 seconds.
9. Complete a separate native verification task. Close the issue only after
   independent current runtime checks agree, then verify issue closure.

Numbers 1 through 9 open stage descriptions, recorded outcomes, controller
history and retained component evidence. Controller history and received OTel
are separate evidence sources. Another demo cannot start before verified closure.

## Check compatibility before adapting resources

The latest connected rehearsal used these installed components:

| Component | Observed version |
| --- | --- |
| Native Kagent controller | `1.0.0-alpha17` |
| Agent Substrate API | `v0.6.0-alpha3` |
| Kyverno admission controller | `v1.17.1` |
| Flux source controller | `v1.6.2` |
| Flux Kustomize controller | `v1.6.1` |

These are a compatibility record, not an office upgrade instruction. The separate
local policy-only proof in the older README used another Kyverno version.

Inspect the installed office CRDs, Agent Card, session API and tool responses.
`live/lab_adapter.py` is an operator adapter for the demonstrated native API. It
uses namespace `kagent`, native session-create CLI flags, `a2a.proto` and
`lf.a2a.v1.A2AService` through plaintext loopback gRPC. The matching native CLI,
`grpcurl`, full proto import tree and an authenticated controller tunnel are
external prerequisites. They are not included as binaries in this source archive.

If the office runtime differs, port `_session`, `_rpc` and task-result parsing to
its existing working adapter. Prove original task and session readback, terminal
states and structured tool artifacts before enabling a fault or repository write.
Do not substitute the legacy native approval protocol for dashboard approval.
Bind `native_address` to the executor's verified controller tunnel for CLI and
gRPC calls. Bind `native_controller_origin` separately to the controller HTTP
origin reachable from the runtime Pod. Set `native_user` to the same verified
partition for session creation, initial HTTP dispatch and task readback. This
partition header does not replace the office's transport authentication. Adapt
that authentication boundary if the existing office adapter requires it.

## Bind the environment

Use these files as inputs, not as apply-ready manifests:

| Input | Use |
| --- | --- |
| [Settings template](office/settings.example.json) | Private operator paths, fixed scope, native names and trusted human identity. Replace human ID placeholders with integers. |
| [SSH argv template](office/ssh-argv.example.json) | Fixed executor and pinned host-key file. Verify the approved operator execution mechanism. |
| [Runtime profile](live/config.example.json) | Actual project, namespace, object identities, policy digests, HTTP hash, required CI and native agent IDs. Its illustrative hashes are not usable proof. |
| [Agent binding contract](office/agent-bindings.example.json) | Exact role tool sets and source skills. Translate this contract to the installed native CRD schema. |
| [Runtime image recipe](office/Dockerfile.runtime) | Build from the Kyverno bundle directory using an approved Python 3.12 base image. Mirror and pin the resulting image. |
| [Runtime resources](office/runtime.example.yaml) | Deployment, Service, PVC and namespaced read-only permissions. |
| [Model budget resources](office/budget.example.yaml) | A separate persistent budget service for the approved model route. |
| [Model budget configuration](office/budget-config.example.json) | Fixed route, model and an operator-approved request allowance. |
| [Flux resources](office/flux.example.yaml) | Bind the existing source credential, branch and dedicated desired-state directory. |
| [GitOps repository files](office/gitops/) | Healthy policy, single-replica application, Service and policy CI. Copy this directory's contents to the dedicated repository root. |

Render every `{{PLACEHOLDER}}` in private files before deployment. Keep credentials
in the office secret manager. Create distinct investigator, reviewer and operator
tokens. The runtime also requires `/config/model.token` and a separate GitLab API
token at `/gitlab/gitlab.token`. Configure the caller credentials through the
existing native MCP secret mechanism. Never copy credentials into the browser.
The bridge derives the dashboard's allowed HTTPS GitLab origin from the trusted
profile's `gitlab_api`. Unrelated hosts remain blocked; the browser cannot select
its own allowed host.

The GitOps example emits `recovered\n` over HTTP and uses
`docker.io/library/busybox:1.36`. The runtime and probes deliberately pin this
image contract. A registry mirror can supply that logical reference. Changing
the reference or HTTP fixture requires a reviewed profile and source adaptation.

Build the image from `work-agent-bundles/kyverno-application-specialist`:

```sh
docker build -f office/Dockerfile.runtime \
  --build-arg PYTHON_IMAGE='{{APPROVED_PYTHON_312_IMAGE_DIGEST}}' \
  -t '{{REVIEWED_RUNTIME_IMAGE}}' .
```

Create the runtime ConfigMap from a filled private profile. Its name must be
`<runtime_deployment>-config`, and its data key must be `config.json`. The bridge
patches that ConfigMap and the runtime Deployment's first container `--data`
argument for each run. `/app` must contain the image's Python modules, `/config`
must contain the profile and tokens, and `/data/runs` must be durable and writable.
Keep these two operator-managed fields out of conflicting Flux reconciliation.
Application and policy changes continue through the dedicated GitOps repository.
Create the budget ConfigMap as `<BUDGET_SERVICE>-config` with the `budget.json`
key from the filled budget configuration. Provision the referenced namespaces,
referenced Secrets and storage before their dependent Deployments. The examples
do not create live credentials or an office ModelConfig. Point the installed
ModelConfig at this budget service's `/v1` endpoint using the approved client
credential, Chat Completions format, `stream: false` and an output limit no higher
than the proxy cap. Verify the gateway accepts the preserved Authorization
header and trace context. The proxy does not forward arbitrary caller headers.
Keep all three native Agents and the classifier on that same bounded allowance.

Put `core.py`, `runtime.py`, `admission.py` and `collect_probe.py` from `live/`
in the private executor's `collector_dir`. The fixed SSH executor also needs
Python, `kubectl`, the scoped kubeconfig and the approved native tools. The lab
adapter uses passwordless `sudo` for fixed commands. Port that execution boundary
if office policy uses a service account, job or another approved executor.

Compute policy digests with `live/core.py:digest` over parsed JSON, not file bytes.
Derive full-document and spec digests for both the healthy and faulty policy.
Set the profile's `policy_file` to `deploy/policy.json`, matching the repository
and CI examples. Keep the settings' `application_file` as `deploy/application.json`
and Flux's desired-state path as `./deploy`.
The faulty fixture differs only in the permitted image pattern
`docker.io/libary/*`. Check the healthy desired spec against the actual admitted
live spec before pinning its digest; API defaulting can differ by Kyverno version.
Set `expected_body_sha256` from the observed baseline HTTP response. Fill agent
IDs as `kagent/<actual-agent-name>` and set the required CI job to `policy-tests`.
Require JUnit cases `valid-image-admitted` and `invalid-image-denied`.
Derive `profile_revision` from the final profile content using `core.digest`,
excluding the `profile_revision` field itself. Do not reuse the illustrative
digest values in `config.example.json`.
Set the initial runtime profile's `run_id` to `office-bootstrap`, matching the
reference Deployment's initial data directory. The bridge creates a different
immutable runtime profile and ledger directory for each actual demo.

The supplied CI script checks the static policy contract. It does not call the
Kyverno admission webhook. Actual positive and negative Kubernetes admissions
are separate mandatory runtime checks.

## Preserve the authorization boundaries

The browser calls only the local bridge. The separate read-only OTel receiver
does not hold GitLab, Kubernetes or approval credentials. The bridge holds the
trusted operator configuration and records the exact-head human decision.

Loopback Host, Origin and CSRF checks plus a configured human ID reproduce the
single-operator rehearsal. They do not establish workplace SSO. Do not expose
this bridge through shared ingress unchanged. A shared office service must bind
the actual authenticated human principal and its approval permissions server-side.
The native `x-user-id` lab convention also needs the office identity binding.

The runtime has investigator, reviewer and operator credentials. It has no
separate executor credential role. Specialist and executor tool separation is
enforced by native Agent allowlists in this implementation. The investigator
endpoint exposes every enabled tool, including the legacy merge tool. Keep
legacy `merge_policy_fix` out of all dashboard Agents. A multi-tenant deployment
needs enforceable per-agent MCP authorization or a reviewed executor capability
split. Do not describe native allowlists as separate backend credentials.

The runtime Kubernetes service account is read-only. The private operator
collector alone has narrowly scoped dry-run Pod permission. Keep its credentials
outside every Agent. Apply the office's existing authenticated MCP routes,
egress grants and network policies. The reference YAML does not prove CNI or SSO
enforcement and does not grant native Agent creation, Pod writes or Secret reads.

## Pass preflight before spending model calls

1. Verify healthy valid admission, invalid-image denial, one ready application
   replica and the expected HTTP body. Record object UIDs and generations.
2. Verify the exact branch head, Flux source artifact, applied revision and Ready
   conditions. Keep policy enforcement active.
3. Verify GitLab API access from the actual runtime and repository Git-fetch
   access through Flux's separate credential. Refresh through the approved
   credential manager without changing account, project or grant scope.
4. Check schedulable capacity for the runtime rollout, budget pod and native
   snapshot or actor setup. Retain completed budget PVCs when retiring idle pods.
5. Verify native Agent readiness, exact tool sets, independent reviewer identity
   and the selected ModelConfig's approved gateway route and credential format.
6. Verify OTLP HTTP JSON traces and logs reach the existing receiver. Prove
   propagation to actual model, skill and MCP operations. A configured exporter
   or mounted knowledge package alone does not prove execution.
7. Allocate a separately approved allowance on durable storage. The fresh lab
   rehearsal used 14 of 16 model requests. That is an observed result, not a
   promised office budget. Failed requests also consume reservations.

The classifier currently pins the `kimi-for-coding` model contract. An origin
override changes the trusted route, not the model contract. If the approved office
model differs, adapt and validate `live/classifier.py` and the budget ModelConfig
before live use. Never introduce a fallback or change the 0.95 admission gate.
Keep streaming disabled. Bind a supplemental allowance to the exact incident
with `model_allowance_run_id`; never reset an existing ledger.

## Verify the extracted source, then the office runtime

From the extracted archive root:

```sh
shasum -a 256 -c SHA256SUMS
python3 -B -m unittest discover \
  -s work-agent-bundles/kyverno-application-specialist/live -p 'test_*.py' -q
python3 -B -m unittest discover \
  -s work-agent-bundles/kyverno-application-specialist/live/budget -p 'test_*.py' -q
python3 -B work-agent-bundles/otel-agent-flow/scripts/verify-bundle.py
python3 -B work-agent-bundles/kyverno-application-specialist/test_package.py
```

Use Python 3.12, Node, Helm and the pinned Python operations dependencies from
`work-agent-bundles/otel-agent-flow/requirements-ops.txt`. Offline tests and
rendering checks do not establish office permissions or runtime behavior.
Keep the receiver accessible to the bridge at loopback port 8792 and the OTLP
HTTP collector at the configured trusted endpoint, for example a separate
loopback tunnel on port 8793. Start `live/flow_server.py` using the command in
`live/DASHBOARD-FLOW.md`. Do not place the two services behind the same public
origin or give the read-only receiver the operator's credentials.

Run one office sandbox incident through the actual dashboard. Retain the
classifier decision, native task bindings, exact-head CI and independent review,
actual human approval, merged SHA, Flux source and applied SHA, stable policy
read bracket, admission and HTTP probes, terminal native verification and closed
issue readback. Show that a second start is blocked while the issue is open.
Prove changed head, missing approval, low confidence, insufficient budget and
failed recovery remain blocked. Use isolated negative drills without replaying
an uncertain write or deleting a ledger.

## Explain these known limits during rehearsal

- Kubernetes backs off Pod creation after repeated denial. Flux can apply the
  healthy policy while the application is still waiting for a retry. Keep the
  recovery gate open until readiness and the measured checks pass. Do not hide a
  manual restart or treat a successful source fetch as application recovery.
- The current stage projection retains the latest 160 observations globally.
  Early stage OTel can disappear during later stages. Controller history and
  descriptions remain available, but full per-stage component retention is not
  implemented. Use the approved observability backend for longer retention.
- MCP interval pairing with an unexported parent is explicitly labelled an
  inference. It cannot establish approval, recovery or closure.
- The initial collector covers this synthetic policy regression. General event
  ingestion, Informer integration and a literal Pi runtime inside Kagent remain
  separate work. The specialist is application-owned; it is not compiled into
  Kyverno or injected by a completed Kyverno admission policy.

Use [VALIDATION.md](VALIDATION.md) for the latest lab evidence. After office
acceptance, record a separate result with the office versions and actual
receipts. Do not rename the lab proof as office validation.
