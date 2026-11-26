# Live evidence: Lookout config review on the home lab, 26 Nov 2026

**Claim:** for a merge request that changes kagent, kro or agentgateway YAML, an agent tests it in a sandbox (main vs MR)
and writes the result back to the merge request **before merge**, citing every high finding. A human then decides.

**Environment:** home-lab kind cluster, kagent 1.0.0-alpha17, agentgateway (Gateway class `agentgateway`), kro 0.9.4,
model GLM 4.6 (`glm-coding`), **mock** GitLab (project `lab/platform-config`, `lookout/lab/mock_gitlab.py`). The lab
cluster plays both the real cluster (read-only reads) and the sandbox (`lookout-mr-*` namespaces). The `main` objects
are copies of live lab objects: the `guard-demo` route and policy, the `ClassicSecureAgent` RGD, the `demo-sentinel`
agent. Client: `lookout_review.py --review config --agent mr-config-review --protocol 1x`.

## Result (final code, after the code review and the re-review)

| MR | What it changes | Expected |
|---|---|---|
| 21 | Adds `guard-demo-status` route with its own auth policy | safe |
| 22 | Loosens `guard-demo-auth` to any ServiceAccount; gives `demo-sentinel` `k8s_delete_resource` | needs changes |
| 23 | `ClassicSecureAgent` RGD stops creating the invoke policy (a valid definition) | needs changes |
| 24 | The same edit made carelessly: a resource still references the removed policy | needs changes |

| MR | Client status | High / medium / info | Findings | Agent run | Tokens in / out | Sandbox run |
|---|---|---|---|---|---|---|
| 21 | `posted` | 0 / 0 / 0 | none | 38 s | 12496 / 1246 | 10.5 s |
| 22 | `posted` | 1 / 1 / 0 | CR-1 agent-write-tools, CR-2 auth-loosened | 39 s | 14166 / 1376 | 10.5 s |
| 23 | `posted` | 2 / 0 / 0 | CR-1 kro-child-missing, CR-2 kro-resource-removed | 80 s | 14908 / 2102 | 20.2 s |
| 24 | `posted` | 2 / 0 / 0 | CR-1 kro-resource-removed, CR-2 kro-rgd-invalid | 64 s | 14864 / 1666 | 19.7 s |

All four notes were posted on the MR; each cites every high finding (the tool server refuses a note that does not).
After the runs: 0 sandbox namespaces, 0 sandbox RGDs, 0 `*.lookout.sandbox` CRDs on the cluster; one janitor CronJob
run found nothing left to remove.

### What only running it showed

- **MR 22:** the loosened route policy does **not** open the route. The parent Gateway's listener policy still limits
  the caller listener to `demo-caller` (stranger 403 before and after). Reported as medium `auth-loosened` with that
  probe as evidence, so the reviewer knows the route's own guard is now only masked.
- **MR 23:** kro renders 12 of 13 children; `AgentgatewayPolicy/demo-invoke` is gone. The invoke route stays
  caller-only today because of the same listener policy.
- **MR 24:** kro rejects the RGD: `references unknown identifiers: [callerPolicy]`. Merged, `ClassicSecureAgent` would
  stop reconciling on every cluster. One high finding, not a cascade of missing children.

## Admission fences (live negative tests, `lookout/lab/negative-config-review.sh`)

12 of 12 behaved as wanted (`NEGATIVE_TESTS_FAILED=0`), impersonating the sandbox ServiceAccount:

| Attempt | Result |
|---|---|
| Create namespace `evil-ns` / ConfigMap in `default` / token for `kagent/default` | DENIED (admission) |
| Read a Secret | DENIED (RBAC) |
| Create a real (non-dry-run) kagent Agent in the sandbox | DENIED (admission); server dry-run ALLOWED |
| Create an RGD outside `*.lookout.sandbox`, or without the `lookout-mr-` name | DENIED (admission) |
| Create sandbox namespace / ConfigMap in it | ALLOWED |
| kro (cluster-admin) renders a sandbox child into `default` | DENIED (`lookout-kro-children-scope`) |
| kro renders a real kagent Agent for a sandbox instance | DENIED (`lookout-kro-children-scope`) |

## Review gates

1. **Design review** (adversarial, before building): REVISE, six blockers; resolutions in `lookout/CONFIG-REVIEW-DESIGN.md`.
2. **Code review** (independent, after the first lab pass): REQUEST CHANGES, 3 high and 10 medium. All 13 fixed, each
   with a regression test (`tests/test_config_review.py`, 36 tests), then this evidence was re-run. The highs were: kro
   could create a real agent for a sandbox instance; an MR that changes an RGD and includes an instance was tested
   against the live RGD; an MR that deletes a Gateway-level policy got the live copy back.
3. **Re-review of the fixes** (same reviewer): all original escapes and false negatives confirmed fixed; one new high
   issue introduced by the fixes: a refused object (for example a policy with remote JWKS) was missing from both sides,
   so an MR's change to it produced no finding and its route probed as open on both sides. Fixed: every refused object
   the MR changes is a `not-tested` finding, and routes whose policy could not be reproduced lose their probe-based
   findings and get `auth-not-tested`. Also fixed: janitor stops on first error, crashes before the guarded block,
   "incomplete" worded as "no change", fixture plural, RBAC-untested instance only in notes, `nodePort`, backendRef
   filters, tighter 403 test, policy host without port. 41 config-review tests; this evidence re-run after that.

## Bugs found by running it (fixed before this evidence)

`Kube.token` name clash (the bearer string shadowed the TokenRequest method); namespace name reuse while terminating
(random run suffix); admission CEL failed on cluster-scoped requests (`has(request.namespace)`); errors on both sides
reported as new (namespace normalised); RGD deleted before its instance leaked a CRD (teardown order); readiness wait
timing out on an empty side; the stranger caller never compared (`lookout-stranger` vs `stranger`); a shorter repeat
answer made the agent write "blast radius not returned" (reverted).

## Not proven

Real GitLab and CI runner for this mode; agentgateway route in front of the agent; a separate sandbox cluster (and the
public-IP question: agentgateway gives the sandbox Gateway a LoadBalancer Service); kagent 0.9 (v1alpha2) agent
manifest; Helm/Kustomize rendering; rate-limit probes; NetworkPolicy enforcement in the sandbox (kind CNI); the model's
own wording is not checked beyond the cite-every-high rule.

## The four notes, as posted

### MR 21

````markdown
<!-- lookout-config-review -->
**Config review (automated, advisory, tested in a sandbox before merge)** · reviewed commit `2121212121212121212121212121212121212121`

**Verdict: Looks safe to merge.**

No findings were raised by the sandbox config review (0 high, 0 medium, 0 info). The probe matrix shows the new route behaves as intended after rollout: anonymous callers are rejected with 401, the authorized caller gets 200, and both the verifier and stranger principals are correctly blocked with 403.

One caveat to keep in mind: the sandbox had to rewrite the real backend, parent Gateway, and subject namespace to run the test (details below), so the production `classic-agents/demo` backend, the `classic-demo` Gateway attachment, and the `classic-agents` namespace binding itself were not exercised — only the route/policy shape and authz behavior were. Since both objects are brand new to the cluster, the worst realistic outcome of any surprise is that this one route doesn't serve traffic; nothing pre-existing is modified.

**What this touches on the real cluster:**
- HTTPRoute classic-agents/guard-demo-status: new to the cluster
- AgentgatewayPolicy classic-agents/guard-demo-status-auth: new to the cluster

---

**Config review (sandbox, before merge)**: 0 high, 0 medium, 0 info.

| ID | Severity | Finding | Evidence |
|---|---|---|---|

**Probe matrix (HTTP status per caller)**

- after `guard-demo-status`: anonymous=401, demo-caller=200, demo-verifier=403, lookout-stranger=403

**Changed for the sandbox (these parts are NOT tested)**

- HTTPRoute guard-demo-status: backend classic-agents/demo -> sandbox echo (backend not tested)
- HTTPRoute guard-demo-status: parent Gateway classic-agents/classic-demo -> sandbox copy
- subject namespace `classic-agents` -> sandbox namespace (SA names unchanged)
````

### MR 22

````markdown
<!-- lookout-config-review -->
**Config review (automated, advisory, tested in a sandbox before merge)** · reviewed commit `2222222222222222222222222222222222222222`

**Verdict: Needs changes before merge** (1 high finding).

**CR-1 (high) — Agent kagent/demo-sentinel gains k8s_delete_resource.** After rollout to every cluster, demo-sentinel goes from read-only/evaluator tools to being able to delete Kubernetes resources, an all-or-nothing destructive permission driven by LLM decisions. Suggestion: keep the deletion path scoped if it's genuinely needed — e.g. restrict deletes by namespace/resource type via policy, or gate behind a human-approval step; otherwise drop this tool from the agent's list.

**CR-2 (medium) — guard-demo-auth no longer names exact callers.** The JWT check changes from `jwt.sub == "system:serviceaccount:classic-agents:demo-caller"` to any service-account subject, so every SA in every namespace could pass this policy. Probes still show stranger=403 / anonymous=401, but that is masked by another policy (e.g. the listener policy), not by this one. Suggestion: keep the exact-subject match (or pin it to a specific namespace/SA set) instead of a broad `startsWith("system:serviceaccount:")`.

**What this touches on the real cluster:** replaces HTTPRoute classic-agents/guard-demo (live policy: guard-demo-auth), AgentgatewayPolicy classic-agents/guard-demo-auth, and Agent kagent/demo-sentinel — all exist and GitOps will overwrite them on merge.

**Not tested:** backend classic-agents/demo (sandbox echo used), parent Gateway classic-agents/classic-demo (sandbox copy), and the `classic-agents` namespace (sandbox namespace; SA names unchanged).

---

**Config review (sandbox, before merge)**: 1 high, 1 medium, 0 info.

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| CR-1 | high | Agent kagent/demo-sentinel gains write tools: k8s_delete_resource | tools before: ['k8s_get_resources', 'k8s_describe_resource', 'k8s_get_events', 'k8s_get_pod_logs', 'k8s_get_resource_yaml', 'k8s_get_cluster_configuration', 'agent:completion-evaluator']; tools after: ['k8s_get_resources', 'k8s_describe_resource', 'k8s_get_events', 'k8s_get_resou |
| CR-2 | medium | AgentgatewayPolicy classic-agents/guard-demo-auth no longer names exact callers | before: ['jwt.sub == "system:serviceaccount:classic-agents:demo-caller"']; after: ['jwt.sub.startsWith("system:serviceaccount:")']; probe after: `guard-demo` stranger=403, anonymous=401 (still denied: masked by another policy, e.g. the listener policy) |

**Probe matrix (HTTP status per caller)**

- before `guard-demo`: anonymous=401, demo-caller=200, demo-verifier=403, lookout-stranger=403
- after `guard-demo`: anonymous=401, demo-caller=200, demo-verifier=403, lookout-stranger=403

**Changed for the sandbox (these parts are NOT tested)**

- HTTPRoute guard-demo: backend classic-agents/demo -> sandbox echo (backend not tested)
- HTTPRoute guard-demo: parent Gateway classic-agents/classic-demo -> sandbox copy
- subject namespace `classic-agents` -> sandbox namespace (SA names unchanged)
````

### MR 23

````markdown
<!-- lookout-config-review -->
**Config review (automated, advisory, tested in a sandbox before merge)** · reviewed commit `2323232323232323232323232323232323232323`

**Verdict: Needs changes before merge** (2 high findings).

**CR-1 (high)** — kro no longer renders `AgentgatewayPolicy/demo-invoke`; the RGD's child count drops from 13 to 12. After rollout, every cluster running this GitOps config will be missing this policy object. Suggestion: confirm the "drop redundant invoke policy" intent is intended for all clusters, or restore the policy template.

**CR-2 (high)** — the ResourceGraphDefinition `classic-secure-agent` no longer creates the AgentgatewayPolicy (template `${schema.metadata.name}-invoke`). Anything that assumed this policy exists (routes, gateway binding, audits) will silently see nothing after rollout. Suggestion: if it is genuinely redundant, remove or update references to it explicitly; otherwise keep the template.

**Probe evidence:** the sandbox probe matrix is identical before and after for all three routes (e.g. `demo-invoke`: anonymous=401, demo-caller=200, demo-verifier=403, lookout-stranger=403), so no probe-visible behavior change — but that does not clear the high findings above.

**What this touches on the real cluster:** ResourceGraphDefinition `classic-secure-agent` exists on the cluster and this MR replaces it (kro re-renders it cluster-wide on merge).

**Not tested:** HTTPRoute backends (rendered as sandbox echo), parent Gateways (sandbox copies), the `${schema.metadata.name}-golden` Job check (replaced by a no-op), the `agent` itself (rendered as a stand-in ConfigMap, never run), and the subject namespace (remapped to a sandbox namespace).

**Config review (sandbox, before merge)**: 2 high, 0 medium, 0 info.

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| CR-1 | high | kro no longer renders `AgentgatewayPolicy/demo-invoke` | before: 13 children, after: 12 |
| CR-2 | high | ResourceGraphDefinition classic-secure-agent no longer creates AgentgatewayPolicy `callerPolicy` | template name: ${schema.metadata.name}-invoke |

**Probe matrix (HTTP status per caller)**

- before `demo-card`: anonymous=401, demo-caller=403, demo-verifier=200, lookout-stranger=403
- before `demo-invoke`: anonymous=401, demo-caller=200, demo-verifier=403, lookout-stranger=403
- before `demo-verify`: anonymous=401, demo-caller=403, demo-verifier=200, lookout-stranger=403
- after `demo-card`: anonymous=401, demo-caller=403, demo-verifier=200, lookout-stranger=403
- after `demo-invoke`: anonymous=401, demo-caller=200, demo-verifier=403, lookout-stranger=403
- after `demo-verify`: anonymous=401, demo-caller=403, demo-verifier=200, lookout-stranger=403

**Changed for the sandbox (these parts are NOT tested)**

- HTTPRoute ${schema.metadata.name}-card: backend ${agent.metadata.namespace}/${agent.metadata.name} -> sandbox echo (backend not tested)
- HTTPRoute ${schema.metadata.name}-card: parent Gateway classic-agents/classic-demo -> sandbox copy
- HTTPRoute ${schema.metadata.name}-invoke: backend ${agent.metadata.namespace}/${agent.metadata.name} -> sandbox echo (backend not tested)
- HTTPRoute ${schema.metadata.name}-invoke: parent Gateway classic-agents/classic-demo -> sandbox copy
- HTTPRoute ${schema.metadata.name}-verify: backend ${agent.metadata.namespace}/${agent.metadata.name} -> sandbox echo (backend not tested)
- HTTPRoute ${schema.metadata.name}-verify: parent Gateway classic-agents/classic-demo -> sandbox copy
- Job ${schema.metadata.name}-golden: image docker.io/library/classic-golden:v1 replaced by a no-op (its own check NOT run)
- RGD classic-secure-agent: agent `agent` rendered as a stand-in ConfigMap; the agent is never run (not tested)
- RGD classic-secure-agent: name and group made unique to this sandbox (kind unchanged)
- subject namespace `classic-agents` -> sandbox namespace (SA names unchanged)
````

### MR 24

````markdown
<!-- lookout-config-review -->
**Config review (automated, advisory, tested in a sandbox before merge)** · reviewed commit `2424242424242424242424242424242424242424`

**Verdict: Needs changes before merge** (2 high findings).

**CR-1 (high)** — The ResourceGraphDefinition `classic-secure-agent` no longer creates AgentgatewayPolicy `callerPolicy` (template `${schema.metadata.name}-invoke` was removed). After GitOps rollout, instances of this kind lose that policy, so the invoke path loses its caller authorization.
Suggestion: either restore the `callerPolicy` template in the RGD, or remove every remaining reference to it — a partial removal is the worst of both.

**CR-2 (high)** — kro rejects this MR's RGD outright: it still references identifier `callerPolicy` that no longer exists ("failed to build dependency graph ... references unknown identifiers: [callerPolicy]"). After rollout the kind stops reconciling on every cluster; in the sandbox nothing rendered at all (16 children and routes missing). This is worse than losing one policy — all instances of this RGD stop being managed.
Suggestion: fix the dangling `callerPolicy` references (most likely a stale name in the dependency graph) so the RGD validates, then re-run this review.

**What this touches on the real cluster**: replaces the existing ResourceGraphDefinition `classic-secure-agent` on the cluster.

**Not tested in the sandbox**: the HTTPRoute backends (replaced by sandbox echo), the parent Gateways (sandbox copy), the golden Job's own check (image replaced by a no-op), and the agent itself (rendered as a stand-in ConfigMap, never run).

---

**Config review (sandbox, before merge)**: 2 high, 0 medium, 0 info.

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| CR-1 | high | ResourceGraphDefinition classic-secure-agent no longer creates AgentgatewayPolicy `callerPolicy` | template name: ${schema.metadata.name}-invoke |
| CR-2 | high | kro rejects the MR's ResourceGraphDefinition; after rollout the kind stops reconciling on every cluster | kro: failed to build dependency graph: failed to extract dependencies: references unknown identifiers: [callerPolicy]; consequence in the sandbox: nothing rendered (16 children and routes missing) |

**Probe matrix (HTTP status per caller)**

- before `demo-card`: anonymous=401, demo-caller=403, demo-verifier=200, lookout-stranger=403
- before `demo-invoke`: anonymous=401, demo-caller=200, demo-verifier=403, lookout-stranger=403
- before `demo-verify`: anonymous=401, demo-caller=403, demo-verifier=200, lookout-stranger=403

**Changed for the sandbox (these parts are NOT tested)**

- HTTPRoute ${schema.metadata.name}-card: backend ${agent.metadata.namespace}/${agent.metadata.name} -> sandbox echo (backend not tested)
- HTTPRoute ${schema.metadata.name}-card: parent Gateway classic-agents/classic-demo -> sandbox copy
- HTTPRoute ${schema.metadata.name}-invoke: backend ${agent.metadata.namespace}/${agent.metadata.name} -> sandbox echo (backend not tested)
- HTTPRoute ${schema.metadata.name}-invoke: parent Gateway classic-agents/classic-demo -> sandbox copy
- HTTPRoute ${schema.metadata.name}-verify: backend ${agent.metadata.namespace}/${agent.metadata.name} -> sandbox echo (backend not tested)
- HTTPRoute ${schema.metadata.name}-verify: parent Gateway classic-agents/classic-demo -> sandbox copy
- Job ${schema.metadata.name}-golden: image docker.io/library/classic-golden:v1 replaced by a no-op (its own check NOT run)
- RGD classic-secure-agent: agent `agent` rendered as a stand-in ConfigMap; the agent is never run (not tested)
- RGD classic-secure-agent: name and group made unique to this sandbox (kind unchanged)
- subject namespace `classic-agents` -> sandbox namespace (SA names unchanged)
````
