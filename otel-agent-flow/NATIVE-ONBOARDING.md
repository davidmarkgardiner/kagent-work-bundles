# Native onboarding observations

The Onboarding tab uses `/api/state` alongside the existing Visual flow and Logs views. It separates current sampled Kubernetes metadata, retained native runtime reads, and a recorded independent GoldenScenario run. It creates no agent, grants no tools, runs no acceptance test, and exposes no new write API or public endpoint.

The existing runtime graph is the main Onboarding view. Select **Skills and knowledge** to filter the actual native calls, or use **Replay trace** to replay received spans. The same graph and details move between tabs, with one renderer and one set of node identities. Readiness cards sit in collapsed details below it. Follow mode selects an exact recorded test trace when retained, otherwise an observed request for the configured agent. Manual selection stays explicit. MCP remains inactive for the current profile, which attaches no MCP tools.

## Observer and viewer

Run the observer outside the credential-free viewer, using an explicitly mounted projected ServiceAccount token and Kubernetes CA:

```sh
python3 onboarding.py observe \
  --plan /plan/reviewed-plan.json \
  --output /observer/onboarding.json \
  --receipt /receipt/golden-onboarding.json \
  --token-file /var/run/onboarding/token \
  --ca-file /var/run/onboarding/ca.crt \
  --interval 3 --ttl 15
```

`--once` performs one observation. The API address is fixed to `https://kubernetes.default.svc`; TLS verifies the mounted CA and redirects are refused. There is no kubeconfig, kubectl, list, watch, discovery, Secret access, or API mutation. Each observation reads the plan's named objects, then rereads their metadata pins and status to reject a changed sample. This reduces torn observations; it is not a transactional Kubernetes snapshot.

Set `ONBOARDING_SNAPSHOT=/observer/onboarding.json` and `READ_ONLY_VIEWER=true` on the existing backend. Mount the shared snapshot **directory** into the viewer read-only. Do not use a file `subPath`: atomic file replacement would leave that mount pointing at the previous inode. Use an `emptyDir` shared with the observer; only the observer mounts the token and CA. Keep pod automatic ServiceAccount mounting disabled, and mount a dedicated projected token only in the observer container. The operator separately supplies the reviewed plan and optional sanitized receipt directory. The image explicitly copies `onboarding.py` and `.dockerignore` allows it.

The public boundary is `read_view(path, now)`; HTTP clients cannot select a Kubernetes URL, filename, or object. Snapshot and receipt files are limited to 128 KiB and use strict metadata schemas. Missing, invalid, future-dated, or expired observations show unknown readiness. Read failures replace previously green state; a stopped observer expires after the configured TTL. The browser also advances expiry if backend polling fails. `sampleErrors` contains only fixed role names and controlled reason codes. Any required sampling error prevents a historical test from applying to current pins. Up to 32 actual sampled stage or pin-fingerprint changes survive observer restart when the existing file validates. No earlier reconciliation transitions are invented.

The observer **does read private object bodies in memory** to hash them: GoldenScenario prompts, AgentTemplate instructions, ConfigMap content, and the fixed profile. Its named `get` permissions therefore grant access to those named bodies. It exports only bounded names, UIDs, generations, hashes, controlled states/reasons, and timestamps. It never exports specs, prompts, instructions, content, status messages, tool arguments/results, proof bytes, or raw exceptions. Package readiness means current controller-reported verified bindings; the observer does not rebuild or independently verify OCI archives.

## Reviewed plan

`onboarding-plan.example.json` is a schema example. Its all-zero hashes are placeholders and must be replaced by reviewed values. `ReviewedPlan.parse()` rejects unknown keys, unsupported API kinds/roles, duplicate roles or API paths, missing required pins, invalid names, and more than 20 objects. The current shape contains one agent and 13 required dependency objects; two optional Flux objects bring it to 15.

Top-level keys are exactly `schemaVersion:1`, `namespace`, `hostedName`, `agentName`, `profileSha256`, and `objects`. Each object has exactly `role`, `apiVersion`, `kind`, `namespace`, `name`, plus `specSha256` for a resource or `dataSha256` for a ConfigMap, and optional `uid`. SHA-256 uses the existing runner's canonical JSON convention: `json.dumps(value, sort_keys=True, separators=(',', ':'))`. `profileSha256` hashes parsed `data['profile.json']`, whereas the profile ConfigMap's `dataSha256` hashes its complete `data` mapping.

Required roles: `hosted`, `skill`, `knowledge`, `skillSource`, `knowledgeSource`, `skillConfigMap`, `knowledgeConfigMap`, `profile`, `template`, `agent`, `model`, `harness`, `golden`. Optional roles `declarations` (GitRepository) and `flux` (Kustomization) must appear together or both be absent. Required objects share the plan namespace. Optional Flux objects may be in another explicitly named namespace. The AgentTemplate name must come from the native controller's canonical template-spec hash; never guess its suffix. Pin existing UIDs. For objects that have not been created, omit `uid`: the observer retains the first observed UID until the reviewed plan fingerprint changes. A replacement remains blocked while that snapshot directory persists. A new pod's emptyDir does not preserve that baseline or history.

Native readiness requires current-generation Accepted, ResolvedRefs, Compatible, EgressPoliciesApplied and Ready, plus equal full desired and successful revisions. The view also requires current HostedAgent, model/profile, skill, knowledge and template dependencies before showing the native agent ready. Hosted readiness requires Accepted and Ready plus current selected release/source/immutable ConfigMap bindings and pinned profile/native specs. The optional Flux lane requires both current Ready conditions, a source artifact matching the GitRepository's pinned commit, and the Kustomization's `lastAppliedRevision` matching that revision.

Give the observer one namespaced Role per referenced namespace. Group each rule by API group **and resource plural**, with only the approved `resourceNames` and `verbs: [get]`; bind it only to the observer ServiceAccount. For example:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: onboarding-observer
  namespace: kagent
rules:
  - apiGroups: [api.kagent.dev]
    resources: [agents]
    resourceNames: [hosted-aks-onboarding-v1]
    verbs: [get]
  - apiGroups: [""]
    resources: [configmaps]
    resourceNames: [hosted-native-profile, "{{REVIEWED_SKILL_CONFIGMAP}}", "{{REVIEWED_KB_CONFIGMAP}}"]
    verbs: [get]
```

This excerpt is incomplete by design: the operator supplies equivalent rules for every exact plan object, including the content sources, releases, model, harness, content-addressed template, HostedAgent, GoldenScenario, and optional Flux resources. A changed dependency name requires a reviewed plan and matching named grant; the reader never widens access automatically.

## Independent recorded Golden receipt

After an independently authorized successful `platform/skills-registry/native/run_golden.py` run, project its private output locally:

```sh
python3 onboarding.py receipt \
  --run-dir /private/actual-native-golden-run \
  --output /receipt/golden-onboarding.json
```

The command only reads existing runner files. It requires `before.json`, `after.json`, `receipt.json`, `scenario.json`, `task.json`, `session-created.json`, and `session-after.json`. It checks identical before/after pins, the canonical receipt dependency hash, Passed and unchanged-dependency flags, native agent/revision/prepared-revision association, exact session/task association and `TASK_STATE_COMPLETED`. It projects metadata for all 13 runner dependency pins and adds the local projection timestamp. Raw input files are also limited to 128 KiB; oversized or malformed runs produce no attestation. The runner raises before writing a passing receipt when acceptance fails, so an absent receipt is unavailable evidence, not a fabricated failed run.

The receipt is an **operator-supplied historical attestation**, not cryptographic verification. Its displayed timestamp is when it was projected locally; existing runner receipts contain no authoritative run timestamp. A record applies to current pins only when all 13 observed UID/generation/spec/data/immutable pins, namespace, agent and full revision match and the snapshot is fresh. Otherwise its real result remains historical. No GoldenScenario status is read, because that CRD has none; no result promotes an agent or admits traffic automatically.

A runtime-link button is enabled only when a retained trace contains matching native agent identity and one native span with both exact `gen_ai.conversation.id` and `a2a.task.id`. Read counts separately include `load_skill` and `load_skill_resource` spans across every exactly matching trace, deduplicated by trace and span identity. Each matching trace has a link. Evicted or missing telemetry stays unknown. Span counts do not establish task completion.

## Connection and limits

Use the existing native CLI session create → invoke → session get flow documented by the runner. The native controller uses **A2A over gRPC**, tenant `namespace/name`, at internal controller port 8083. The displayed internal address is connection metadata, not a browser REST endpoint. This feature neither uses the legacy `/api/a2a` route for native onboarding nor changes existing runtime routes.

The demo remains one reviewed runtime/model/harness profile, one Skill, one KnowledgeBase and zero operational tool grants. Both packages are delivered through the native OCI skill mechanism. A conversational catalog request → review/Git → Flux → controllers → independent test → connection-details flow is explicitly proposed architecture; there is no active creator or arbitrary BYO provisioning.

Run focused behavior and full existing bundle checks from this directory:

```sh
python3 -m unittest test_onboarding -q
python3 scripts/verify-bundle.py
```

These are local/offline checks. Deployment, live observer authorization, actual mounted hashes, a fresh onboarding lifecycle, and the independent live Golden run require separate runtime evidence.
