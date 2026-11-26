# Lookout config review: test platform YAML on a sandbox before merge

Status: **built and lab-proven on 2026-11-26** (kagent 1.0.0-alpha17, agentgateway, kro 0.9.4, GLM 4.6, mock GitLab).
Decided with David on 2026-11-26. Review gate: an adversarial Opus review (Kimi proxy was down) returned REVISE; its
blockers are resolved in the build, see "Review gate outcome" and "As built" at the end. Evidence:
`evidence/LIVE-CONFIG-REVIEW-LAB-2026-11-26.md`.

## Intent

Lookout already gives each merge request an advisory security review by reading the diff. For MRs that change
**platform config** (agentgateway routes and policies, kagent agents, ModelConfigs, MCP servers), reading the YAML is
not enough. The useful question is "what will this do to the cluster?", and only the cluster can answer it.

Config review mode does that **before merge**:

1. Read the changed YAML from the MR, and nothing else from the repo.
2. Look at the real cluster, read-only: what the change replaces, what it targets, and what depends on it.
3. Apply the YAML in a throwaway namespace on a sandbox cluster that has the same GitOps base, and run tests.
4. Post one MR note with the evidence: "this changes X; tested: results; add Y; you probably don't need Z."

A human still reviews and merges. Lookout never approves, merges, or touches the real cluster.

Inspiration: Solo.io's agentshield (announced 2026-10-22) checks live state rather than git, runs rules on every
change, uses a model only for novel risk, and applies nothing without a person's approval and an admission dry-run.
We take the same position, moved earlier: test on a sandbox *before* the change reaches the cluster.

Prior work: `work-agent-bundles/agentshield-kagent-poc/` (27 Oct 2026, branch `feat/agentshield-native-poc-20261027`,
not on main) ran AgentShield on the Proxmox lab and proved **post-change** drift detection with a bounded handoff to a
kagent agent. The two are complementary: Lookout config review catches the change before merge; AgentShield catches
drift and changes that never went through an MR. Reuse from it: the bounded evidence packet
(`runtime/scripts/pack_findings.py`), the read-only observer ServiceAccount pattern, and its test shape (baseline,
benign control, bad change, rollback).

## The litmus test (acceptance)

`main` is what rolls out to every cluster through GitOps, so the MR is the last point a human can stop a bad change.
Config review is done when, for an agent, kro, or agentgateway MR:

1. The finding is **on the MR before merge**, as one note the reviewer reads in place.
2. Every claim in the note is backed by something run on the sandbox (a status, a probe result, a before/after
   comparison), not by reading the YAML.
3. A known-bad MR (a route left open, an agent given write tools, a kro definition that drops a policy) is flagged,
   and a known-good MR is not. Lookout never blocks or merges; the human decides.

## Our version of AgentShield: compare before and after

AgentShield's value is the graph: which callers can reach which agents, tools, and models, and what policy governs
each path. Config review builds the same picture twice in the sandbox and reports the difference:

- **Before**: the MR namespace with the `main` versions of the changed objects (the same GitOps base).
- **After**: the same namespace with the MR versions applied.

For each, the sandbox MCP records, in code: routes and the policies attached to them, callers allowed per route,
agents behind each route and their tool sets, ModelConfigs and the backends they reach, and NetworkPolicy reach.
Probes confirm the edges that matter (a denied call really gets 403). The note leads with the difference, for example:
"after this MR, `caller-b` can reach `sentinel-worker`, which has write tools (was 403, now 200)" or "route
`a2a-lookout` loses its rate limit". New reach to an agent with write tools, or to a model backend, is always flagged.
A model explains the difference. It does not decide it.

## Scope: which changes get config review

Three families, chosen by David on 2026-11-26. Skills and tools are **out of scope for now** (their repo is not decided).

| Family | Kinds | Example in our repos |
|---|---|---|
| kagent | `Agent`, `ModelConfig`, `RemoteMCPServer`, `MCPServer`, `AgentTemplate` (groups `kagent.dev` v1alpha2 and `api.kagent.dev` v1alpha3) | Sentinel worker, Lookout's own agent |
| kro around kagent | `ResourceGraphDefinition` (`kro.run`) whose resources include any kind above, **and** instances of those RGD kinds | DICE `ClassicSecureAgent`: Agent + 3 ServiceAccounts + NetworkPolicy + AgentgatewayPolicies + HTTPRoute |
| agentgateway | `Gateway`, `HTTPRoute`, `AgentgatewayPolicy`, `AgentgatewayBackend` | `lookout/gateway/route-lookout.yaml`, Guard block policies |

Detection is **by kind in the changed files, not by path**, so the same CI template works whichever repo the YAML
lives in. The client parses the MR's changed YAML (multi-doc) and picks the mode: any in-scope kind means config
review, otherwise the normal Lookout review. A mixed MR gets both sections in the one note. Helm templates and Kustomize
overlays are rendered first (`helm template` / `kustomize build` at the MR head, in CI), and the rendered output is
what gets tested. If rendering fails, that is the first finding.

## kro: test the definition by using it

An RGD is cluster-scoped and generates a CRD, so it cannot simply go into the MR namespace. The sandbox MCP:

1. Renames the RGD and its generated kind per MR (`ClassicSecureAgent` becomes `LookoutMr123Abc1234ClassicSecureAgent`,
   with the name prefixed `lookout-mr-`). Then two MRs never collide, and the real kind is never touched.
2. Applies it, waits for the RGD to be `Active` (kro validated the graph and the CEL expressions), and records the
   generated CRD.
3. Creates **one instance** in the MR namespace from a fixture. It uses the example instance in the MR if there is
   one, otherwise the minimal values from the RGD schema's defaults.
4. Checks that kro rendered every child resource it should (Agent, ServiceAccounts, NetworkPolicy, policies, route),
   that each child reports Ready/Accepted, and then runs the normal probe catalogue against the rendered route and agent.
   This catches the typical kro bug: the definition is valid, but a child it renders is wrong or missing.
5. Teardown deletes the instance, then the RGD (and with it the generated CRD).

When an MR changes only an **instance** of an existing RGD, the sandbox uses the RGD already installed on the sandbox
(same GitOps base) and tests the instance in the MR namespace.

kro needs cluster-scope rights, so RBAC alone is not enough (RBAC cannot restrict `create` by name prefix). The sandbox
cluster carries a `ValidatingAdmissionPolicy` that lets the Lookout ServiceAccount create only RGDs named `lookout-mr-*`
whose generated kind starts with `LookoutMr`, and nothing else cluster-scoped.

## Why not repo browsing

The six-tool repo browsing made large MRs expensive (around 25k input tokens per review, about 97k on a big MR) and
still partial. A platform-config MR is small and self-contained. Its risk is in how it interacts with the cluster, not
in the rest of the repo. Config mode therefore drops `list_tree`/`search` and uses the cluster instead.

## Flow

```
MR opened/updated (paths match platform config)
  -> CI job: A2A pointer {project, mr_iid, head_sha}         (unchanged Lookout client)
  -> agent mr-config-review
       GitLab MCP (existing shim):  get_mr, get_mr_diff, get_file, get_review_state, post_note
       k8s READ MCP -> real target cluster: get/list/describe only
       sandbox MCP  -> sandbox cluster, pinned in code to namespace lookout-mr-<iid>-<sha7>
            sandbox_apply(yaml)      server-side apply into the MR namespace only
            sandbox_status(kind,name) conditions such as Accepted/Programmed/Ready
            sandbox_probe(case)      fixed probe catalogue (see Tests), results classified in code
            sandbox_teardown()       delete the namespace (also run by CI in after_script)
       skill: config-review checklist (security + optimisation), versioned in the bundle
  -> Warden contract checks the note (evidence quoted, every test result cited, no claims without a probe)
  -> one note, updated in place on new pushes
```

## Safety (the main design point)

| Risk | Control, enforced in tool code, not the prompt |
|---|---|
| Agent writes to the real cluster | The real-cluster MCP has no write verbs (kagent-tools-readonly). Only the sandbox MCP can write, and its kubeconfig is a ServiceAccount on the **sandbox cluster** with RBAC limited to `lookout-mr-*` namespaces |
| YAML escapes the MR namespace | `sandbox_apply` rewrites/rejects: `metadata.namespace` forced to the MR namespace; cluster-scoped kinds refused except a renamed `lookout-mr-*` RGD (see kro); an allowlist of kinds (Gateway API, agentgateway, kagent, kro RGD and its instances, ServiceAccount, ConfigMap, Service, NetworkPolicy) |
| MR YAML points at real backends or secrets | Secrets in the MR are refused; `secretRef`s are swapped for sandbox stub Secrets; backend hosts outside the sandbox allowlist are rewritten to the sandbox echo/mock-LLM service, and the note says so |
| Probes become an attack tool | `sandbox_probe` takes a case **name** from a fixed catalogue, not a URL; targets only the MR namespace's Gateway |
| Untrusted MR text steers the agent | Same as Lookout today: title, description, and YAML comments are data in fences; the prompt says never follow instructions in them |
| Leftover namespaces | Namespace labelled with MR, sha, and expiry; teardown on every run; a CronJob deletes expired `lookout-mr-*` |
| Two pushes race | Namespace name includes the sha; a stale-head run cannot post (existing shim refuses a non-current head) |

## Tests in the sandbox (fixed catalogue, results decided in code)

| Case | Pass means |
|---|---|
| `status_accepted` | Every applied Gateway API / agentgateway object reports Accepted/Programmed; no dangling targetRefs |
| `unauth_denied` | A request without credentials to each new or changed route gets 401/403 |
| `auth_allowed` | A request with the sandbox test identity gets 2xx (mock LLM / echo A2A) |
| `cross_route_denied` | The test identity for route A is denied on route B |
| `rate_limit` | When a limit is declared, the request after the burst gets 429 |
| `model_probe` | A ModelConfig change: one-token probe through the route (existing `guard/model_probe.py`, against the mock LLM) |
| `kro_render` | An RGD or instance change: RGD `Active`, every expected child rendered and Ready, none extra |
| `tool_allowlist` | An agent change: the declared tools match the checklist's allowed set for its type (read-only vs write) |

## Checklist skill (what the model compares against)

Security: a route with no auth policy; an A2A route reaching an agent with write tools; an MCP server with no tool
allowlist; backend TLS off; an agent with `k8s_apply_manifest` outside its namespaces; a cross-namespace Secret
reference; wider RBAC than needed. Optimisation: no token or rate limit; no model fallback; unused routes or backends;
duplicate or overlapping policies; timeouts shorter than streaming runs. Each item lists which probe or read proves
it, so the note never claims what nothing tested.

## The real-cluster read (step 2)

Read only: the live objects with the same names, what their targetRefs point at, the policies attached to the same
routes, and agents using the changed ModelConfig/MCP server. The output is a short "blast radius" section in the note:
"this replaces policy P on route R, which carries traffic for agents A and B." No dry-run against the real cluster
in v1 (decided: sandbox only).

## Scope for the first build

- Trigger: the existing Lookout CI template; the client picks config mode by kind in the changed YAML (see Scope).
- New: `lookout/sandbox_mcp.py` (4 tools, stdlib + kubectl), its RBAC and manifest, the probe catalogue, the
  config-review agent (v1alpha2 and v1alpha3), the checklist skill, and a Warden contract for the note.
- Lab proof on the VM 201 kind cluster: one good MR (adds a route with auth and a limit; all probes pass) and one bad
  MR (a route with no auth policy and an agent with write tools; the note flags both with probe evidence), plus one
  kro MR (a `ClassicSecureAgent` change that drops the caller policy; `kro_render` and `unauth_denied` catch it). Plus negative
  tests: cluster-scoped kind refused, namespace escape refused, Secret refused, external host rewritten, teardown run.

## Open questions

1. Which sandbox at work: a dedicated small cluster, or a sandbox-only node pool and namespace prefix on an existing
   non-prod cluster? The second is cheaper but shares the agentgateway controller with real traffic.
2. Does the sandbox track the same GitOps base automatically (Argo app-of-apps pointed at `main`), so its baseline
   matches the real cluster?
3. Air-gap: the mock LLM and echo backends need images in the inventory.
4. kro version on the sandbox must match the real cluster, or `Active` on the sandbox proves little.
5. Skills and tools: add later as a fourth family once their repo is decided.

## Review gate outcome (2026-11-26)

An adversarial review returned **REVISE** with six blockers. How each was resolved in the build:

| Blocker | Resolution |
|---|---|
| kro creates children with its own (cluster-admin) rights, so fences on the sandbox ServiceAccount do not cover them | The engine walks every RGD template: kind allowlist, namespace must be `${schema.metadata.namespace}`, no RBAC, Secrets or cluster-scoped kinds. A second admission policy (`lookout-kro-children-scope`) denies any child of a `*.lookout.sandbox` instance outside `lookout-mr-*`. Proved live: kro tried to write into `default` and was denied |
| References to other namespaces were not rewritten | Refused (agent tool servers, model configs, policy targets) or rewritten and listed as not tested (parent Gateway, backends) |
| "Same GitOps base" could put real secrets in the sandbox | Stated as a requirement for the work sandbox: a sanitised overlay with no real credentials. The lab is one cluster and says so |
| Applying the YAML runs code (BYO images, MCPServer, kro Jobs) | BYO agents refused; kagent objects only server-side dry-run (enforced in code AND by admission); kro Jobs neutralised (no-op image, no projected token); `pod-security` baseline on sandbox namespaces |
| The model was in the apply path | The model passes only `{project, iid, head_sha}`; the server fetches the YAML; findings are decided in code; the note is refused unless it cites every high finding |
| Auth rewrites could hide a bad issuer/audience/subject | Only the namespace part of a ServiceAccount subject that names the object's own namespace is rewritten; issuer, audience and JWKS are untouched (unit-tested) |

Also adopted: rename the kro **group**, not the kind; before and after are symmetric (main's RGD goes in under its own
group); deletions are honoured; every route on either side is probed; the parent Gateway's own policies are part of
both sides; generated CRDs are deleted at teardown (kro has no `--allow-crd-deletion` on the lab).

## As built (2026-11-26): what changed from the design above

- **One tool does the sandbox work.** `lookout_config_review(project, iid, head_sha)` replaces the four
  `sandbox_*` tools. The agent has three tools: `lookout_get_mr`, `lookout_config_review`, `lookout_post_note`.
- **Two namespaces per run**, `lookout-mr-<iid>-<sha7>-<run>-b` (main) and `-a` (MR), set up in parallel. A random
  run suffix stops a re-run colliding with a namespace that is still terminating.
- **Probes:** every route on both sides, as anonymous, `lookout-stranger` (named by no policy), and every ServiceAccount
  a policy names (tokens minted in the sandbox namespace, with the policy's audience). 401/403 = denied, 429 = limited,
  5xx = unreachable, anything else from the echo backend = allowed.
- **kro:** the instance comes from the MR if it has one, otherwise from the first live instance of the original kind
  (read-only), and the note says which. The agent node's `readyWhen` is dropped (the sandbox never runs the agent) and
  listed as not tested. An RGD that kro rejects is one high finding quoting kro's message, not a cascade.
- **Findings found only by running it**: MR 22's loosened route policy is masked by the listener policy on the parent
  Gateway (the probe shows the stranger still gets 403), so it is reported as medium `auth-loosened` with that evidence,
  not as an open route. MR 24's RGD is rejected by kro (`references unknown identifiers: [callerPolicy]`); reading the
  diff does not show that.
- **Teardown order:** instances first (kro removes them and its finalizer while the RGD exists), then the RGD, the
  generated CRD and the namespaces. Clearing the finalizer is a last resort and is noted. First live run leaked one CRD
  because the RGD went first; fixed and re-run clean.
- **Repeat tool calls** return the same cached evidence (one sandbox run). A shorter "already returned" answer was tried
  and reverted: the live agent then wrote "blast radius not returned" in the note.
- **Not built:** Helm/Kustomize rendering (a templated file is reported as not tested), a NetworkPolicy baseline in the
  sandbox namespaces (kind's CNI), a real GitLab and CI runner for this mode, a separate sandbox cluster, kagent 0.9
  (v1alpha2) manifests for the agent, rate-limit probes, and the Warden contract for the note (the cite-every-high rule
  in `lookout_post_note` is the gate for now). The janitor CronJob was added after the code review (below).

## Code review outcome (2026-11-26, after the first lab pass)

An independent code review returned **REQUEST CHANGES** (3 high, 10 medium). All were fixed, each with a regression
test, and the lab evidence was re-run on the fixed code.

| Finding | Fix |
|---|---|
| HIGH: kro creates children with its own rights, so a kro instance created a **real** kagent Agent | kro agent templates are rendered as a stand-in ConfigMap (tools and model recorded); a graph that reads the agent's spec or status is refused as not tested; `lookout-kro-children-scope` also denies kagent objects and workloads (proved live); a `pods: 4` ResourceQuota per sandbox namespace |
| HIGH: an MR that changes an RGD and includes an instance was tested against the live RGD | a live RGD is never added when an RGD in the MR (base or head) defines the kind |
| HIGH: an MR that deletes a Gateway-level policy got the live copy back | live context objects the MR defines, changes or deletes are never added; a namespace-less MR object matches by kind and name |
| Non-Gateway `parentRefs` kept their namespace | parentRefs replaced with the sandbox Gateway (section name kept); others dropped and listed as not tested |
| Service `externalIPs`/`loadBalancerIP`, CEL `type` | only selector and ports kept, type ClusterIP |
| Probes followed redirects with the token | no redirects followed |
| 404 counted as allowed; host/header/method matches never probed | probes send the route's host, method and exact headers; the echo marks its answers, so a gateway 404 is `no-match` and reported as not tested |
| Policy `extAuth`/backend refs and remote JWKS not fenced | other namespaces and remote JWKS refused; backend refs and hosts pointed at the echo |
| Malformed YAML or CEL-valued lists crashed the run (no note) | refused per object; invalid YAML is a high finding; any crash still ends in a note (`review-incomplete`) |
| File cap applied before the YAML filter | YAML filtered first, diffs paged, `incomplete` reported |
| Teardown stopped at the first error; no janitor | every step guarded; janitor CronJob (`config_review/janitor.py`) removes expired namespaces and old RGDs/CRDs |
| Plural guessed as kind + "s" | read from the generated CRD (code and deploy script) |
| New RGD kinds have no RBAC (403 reported as a high finding) | reported as "not tested: add its plural to INSTANCE_PLURALS" |
| Lows | wait for policies Accepted; `/evidence` only with `LOOKOUT_DEBUG_EVIDENCE=1` and a bounded cache; new open route reported once; template `kro.run/*` labels stripped; "before" is the merge base (documented below) |

Still open: "before" is the MR's merge base (`diff_refs.base_sha`), not the current tip of `main`; on a cloud sandbox,
agentgateway gives the sandbox Gateway a LoadBalancer Service, so the work sandbox needs internal-only load balancers or a
ClusterIP parameters ref for the Gateway.

## Re-review outcome (2026-11-26)

The same reviewer re-checked every fix against the code: the original escapes and false negatives were fixed, but the
fixes introduced one high issue. A refused object (for example a policy with remote JWKS, common in production) was
missing from both sides, so an MR's change to it produced no finding, and its route probed as open on both sides.
Fixed: every refused object the MR changes or adds is a `not-tested` finding; routes governed by a policy that could
not be reproduced (a Gateway-level policy means every route) lose their probe-based findings and get `auth-not-tested`.
Also fixed from the re-review: the janitor stops on the first error; a crash before the guarded block left no note
(`run_review` now always returns evidence after the fetch); "incomplete" was worded as "nothing changed"; the fixture
registered a guessed plural; an RBAC-untested instance appeared only in notes; `nodePort` on a ClusterIP Service;
backendRef filters; a tighter RBAC 403 test; a policy `host` rewrite with a port.

Final verdict of the re-review: **APPROVE** (no medium or high issues). Its low notes: `targetSelectors` policies and a
malformed expiry label in the janitor are now handled; still open (low): when a route was protected only by a policy
the sandbox could not reproduce, a probe-level high is reported as two medium findings (`auth-not-tested` plus
`not-tested`/`deleted`); the wording is honest, the severity could be higher.
