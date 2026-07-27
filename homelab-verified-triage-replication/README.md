# Evidence-first worker → management triage — verified replication bundle

One self-contained folder. Deploy it, verify it, smoke-test it, tear it down.

```text
worker cluster       Alloy ──▶ Vector ──▶ Confluent Kafka
                     (logs +   (redact,    (topic k8s-events)
                      events)   envelope,
                                dedupe)
                                    │
management cluster   Argo EventSource ──▶ Sensors ──▶ WorkflowTemplate
                                                          │
                              validate ▶ claim ▶ read-only kagent ▶ GitLab work item
```

The agent **diagnoses only**. It never applies, patches, deletes, execs, scales
or remediates. Every envelope carries `automation_allowed: false` and the
Sensors filter on it.

---

## Status

Deployed and verified end to end on the `red` homelab cluster on **2026-07-24**,
against **real Confluent Cloud** and a **real gitlab.com project** — not mocks.
Both signal paths (pod logs and Kubernetes events) were proven, plus dedup,
redaction, agent-failure handling and concurrency.

Three correctness defects were found in the previously-"proven" config during
that run and fixed here. Read **[FINDINGS-AND-FIXES.md](FINDINGS-AND-FIXES.md)**
before you deploy this anywhere that matters — especially F0, which explains why
the config in this folder differs from what you may have been about to copy.

Evidence for every claim: **[evidence/VERIFICATION-2026-07-24.md](evidence/VERIFICATION-2026-07-24.md)**.

---

## Layout

```
README.md               you are here — what it is, prerequisites, how to port it
FINDINGS-AND-FIXES.md   what was wrong, what was fixed, what is deliberate
RUNBOOK.md              one page: what to do when something looks wrong
RESTART-SAFETY-AND-DELIVERY-VERIFICATION.md
                       work-agent handoff for proving delivery and persisting
                       Alloy positions without assuming Vector disk buffering
config/                 the five manifests, in apply order (+ kustomization)
fixtures/               disposable pods that generate real log + event signals
scripts/                deploy / verify / smoke-test / teardown, all context-explicit
evidence/               the verification run: commands, output, ticket bodies
```

---

## Prerequisites

These are **not** created by this bundle and are checked by `deploy.sh` before
anything is applied:

| What | Where | Notes |
|---|---|---|
| Namespaces `argo-events`, `monitoring`, `kagent` | both clusters | |
| Argo Events + Argo Workflows, EventBus `default` | management | CRDs `sensors`, `eventsources`, `workflowtemplates` |
| ServiceAccount `argo-events/argo-events-sa` | management | needs create/get/replace/patch on ConfigMaps in `argo-events`, and create on Workflows |
| ServiceAccount `monitoring/alloy` + ClusterRole | worker | pod + event read |
| Secret `argo-events/confluent-credentials` | worker + management | keys: `bootstrap`, `key`, `secret` |
| Secret `argo-events/gitlab-credentials` | management | keys: `url`, `token`, `project-id` |
| kagent Agent `kagent/k8s-readonly-agent` | management | read-only tools only |

**No credential is in this bundle.** Every secret is a `secretKeyRef`. Keep it
that way — fill real values in your approved secret store, never in Git.

---

## Run it

### Phase 1 — make the direct Kustomize deployment work

This is the first work-agent path. Keep it in a bounded non-production
environment until the smoke test creates a real, evidence-rich GitLab work item.
The manifests are already a native Kustomize unit; deploy the rendered bundle,
not individual YAML files:

```bash
kubectl --context <ctx> kustomize config/                 # inspect what will apply
kubectl --context <ctx> apply --dry-run=server -k config/ # API/schema gate
kubectl --context <ctx> apply -k config/                  # direct non-production deploy
bash scripts/verify.sh     --context <ctx>                # read-only health + wiring
bash scripts/smoke-test.sh --context <ctx>                # real log + event -> real ticket
```

`scripts/deploy.sh` performs the same deployment after an explicit prerequisite
gate; it uses `kubectl apply -k config/`. Use it when you want the preflight
checks as part of the direct deployment.

### Phase 2 — make credentials repeatable

Do not add rendered Secrets to this repository. The direct deployment expects
these Secret *names and keys* to exist already; this is the contract an
External Secrets Operator implementation must satisfy:

| Target Secret | Namespace | Required keys | Used by |
|---|---|---|---|
| `confluent-credentials` | `argo-events` | `bootstrap`, `key`, `secret` | Vector producer and Argo Kafka consumer |
| `gitlab-credentials` | `argo-events` | `url`, `token`, `project-id` | workflow ticket creation/update |

Once the direct path works, add the approved `SecretStore`/`ClusterSecretStore`
and `ExternalSecret` resources for those exact contracts. Validate that ESO has
created and refreshed both Secrets before applying the triage `config/` bundle.
The secret backend, identities, and remote secret names are environment choices;
they must remain outside these public manifests.

### Phase 3 — promote the proven overlay to Flux

Only promote after Phase 1 has passed. Commit the Kustomize configuration,
ExternalSecret definitions, runbooks, fixtures, and captured verification
evidence; never commit resolved credentials or a rendered `values.env`. Then
have Flux reconcile the same overlay that passed direct apply, and repeat
`verify.sh` plus the smoke test through the Flux-managed deployment. Git becomes
the promotion boundary and Flux becomes the ongoing reconciler—not a second,
different deployment design.

### Script shortcuts

```bash
bash scripts/deploy.sh      --context <ctx>   # preflight, then apply
bash scripts/verify.sh      --context <ctx>   # read-only health + wiring + counters
bash scripts/smoke-test.sh  --context <ctx>   # fire fixtures, prove end to end
bash scripts/teardown.sh    --context <ctx>   # remove everything this bundle made
```

`--context` is mandatory on all four. A shell's default context is not proof of
intent, and this creates real tickets.

`verify.sh` exits non-zero if any component is unhealthy, so it works as a cron
or CI check. It is safe to run at any time — it mutates nothing.

`smoke-test.sh` **creates real GitLab work items**. That is the point of it.
Close them afterwards; they all carry the `automated-triage` label.

## Workflow housekeeping

The shipped `red-agentic-triage` WorkflowTemplate is deliberately bounded:

| Object | Policy | Why |
|---|---|---|
| Completed workflow Pods | Argo `podGC: OnPodCompletion` after a five-minute delay | Leaves a short inspection window, then prevents pod accumulation. |
| Successful Workflow CRs | Argo TTL: one hour | Retains enough run history for normal smoke-test inspection without retaining thousands of completed runs. |
| Failed Workflow CRs | Argo TTL: 24 hours | Preserves failure evidence for investigation before cleanup. |

`verify.sh` fails if this policy is absent or altered. This is the per-workflow
guardrail; it does not replace a one-off cleanup of any historical backlog that
already exists in a cluster. For an existing backlog, start with the dry run in
[`../argo-workflow-retention-cleanup/`](../argo-workflow-retention-cleanup/README.md)
and scope it to the triage namespace/labels before approving deletion.

---

## Porting to work — what you must change

Nothing in `config/` is parameterised, on purpose: you should read each value and
choose it, not template past it.

1. **`config/00-namespace.yaml` + `01-alloy.yaml`** — replace
   `agentic-triage-proof` (3 occurrences) with your approved non-production
   namespace. Start with exactly one.
2. **`config/01-alloy.yaml`** — `cluster = "red"` and `environment = "lab"` in
   both `stage.static_labels` blocks. `cluster` is the worker identity that ends
   up in the ticket and in the `kubectl --context <cluster>` reach-back block, so
   make it the name a human would actually type.
3. **`config/02-vector.yaml`** — the `CONFLUENT_TOPIC` value, and the fallback
   `.cluster = … ?? "red"`.
4. **`config/03-argo.yaml`** — the EventSource `url`, `topic` and
   `consumerGroup.groupName`; and in `validate-schema` the allow-listed
   `cluster` (`case "$cluster" in red)`) — this is the guard that stops another
   cluster's traffic being ticketed as yours, so it must match item 2.
5. **`config/03-argo.yaml`** — `AGENT_URL` in `diagnose-readonly` if your agent
   is not named `k8s-readonly-agent`.
6. **Resource names.** Everything is prefixed `red-` / `triage-`. Rename if that
   collides with an existing pipeline. The Sensors reference the EventSource by
   name, and the WorkflowTemplate by name — change all of them together.
7. **Confluent identity + ACLs.** The pilot uses one service account for produce
   and consume. Work will want separate produce/consume principals with topic
   ACLs.
8. **Claim durability.** The 24h dedupe claim is a ConfigMap in `argo-events`.
   That is honest for a pilot and is *not* a durable TTL store. If your platform
   requires one, that is the one substantive rewrite — the interface is small
   (`claim-24h-window` reads/writes five keys and does one CAS `replace`).

## What each file owns

| Path | Responsibility |
|---|---|
| `config/00-namespace.yaml` | The deliberately narrow proof namespace that generates and scopes worker signals. |
| `config/01-alloy.yaml` | Collects selected pod logs and Kubernetes events, enriches them with worker identity, and sends them to Vector. |
| `config/02-vector.yaml` | Redacts and normalises the signals into the v2 evidence envelope, meters drops/deduplication, and produces to Kafka. |
| `config/03-argo.yaml` | Consumes Kafka, separates log/event routing, validates and claims incidents, calls the read-only agent, and creates or appends GitLab work items. |
| `config/04-workflow-concurrency.yaml` | Sets the shared workflow semaphore so an incident burst cannot overwhelm the management plane. |
| `config/kustomization.yaml` | The single direct-apply and eventual Flux entry point; use `kubectl apply -k config/`. |
| `fixtures/` | Safe disposable log, crashloop, replay, and broker scenarios used by the smoke test. |
| `scripts/deploy.sh` | Explicit context/prerequisite gate followed by the Kustomize apply. |
| `scripts/verify.sh` | Read-only component, wiring, counter, and agent-health verification. |
| `scripts/smoke-test.sh` | Generates a real log and event signal and proves the full route through to GitLab. |
| `scripts/teardown.sh` | Removes only this proof path and its generated state; preserves prerequisites and tickets. |
| `FINDINGS-AND-FIXES.md` | The live defects found in the earlier proof configuration and the fixes packaged here. |
| `evidence/VERIFICATION-2026-07-24.md` | The command/output evidence for the homelab end-to-end run. |
| `RUNBOOK.md` | Operator triage when verification or smoke testing is not healthy. |

---

## Reading the output

**A good ticket** carries: a severity header, the fingerprint, cluster /
namespace / node / pod / container / service, reason + severity + signal kind,
first and last seen, the redacted evidence, a copy-paste `kubectl` reach-back
block aimed at the worker, and a non-empty agent analysis.

**A ticket labelled `triage-agent-unavailable`** means the agent backend failed
for that incident. The evidence and reach-back block are still correct; only the
analysis is missing, and the ticket says exactly why. Investigate the agent, not
the pipeline. Find them all with:

```
GET /projects/:id/issues?labels=triage-agent-unavailable&state=opened
```

**Deduplication** is four layers, and you can see each one:

| Layer | Where | What it collapses |
|---|---|---|
| `delivery_key` dedupe | Vector | identical repeats of the same signal |
| `dedupe_key` claim | `claim-24h-window` | any signal for the same pod within 24h |
| in-flight poll | `claim-24h-window` | a sibling workflow racing on the same pod |
| fingerprint label search | `create-gitlab-issue` | anything that slips past the above |

The first is a counter on `:9598`; the rest are visible in workflow logs and in
the `triage-dedupe-*` ConfigMaps.

**Quarantine (DLQ).** Records with an unknown schema, an unexpected cluster, or a
timestamp older than 24h are written to a labelled ConfigMap with the original
envelope preserved, not dropped:

```bash
kubectl -n argo-events get cm -l triage-quarantine=true
```

---

## Provenance

Derived from `work-agent-bundles/evidence-first-worker-triage/next-phase-end-to-end/`,
specifically the `reference-config/` set — see FINDINGS-AND-FIXES.md **F0** for
why that set and not `applied-config/`, and why the `kustomize/` + `templates/`
v3 track must not be mixed with it.
