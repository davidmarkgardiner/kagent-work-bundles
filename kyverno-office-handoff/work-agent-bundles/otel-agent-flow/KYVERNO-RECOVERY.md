# Connect the Kyverno recovery proof to the OTel dashboard

For the complete dashboard-controlled office rehearsal, start with
[the office handoff](../kyverno-application-specialist/OFFICE-HANDOFF.md).
The read-only Recovery view described below is separate from the trusted
operator bridge that records dashboard approval and dispatches native work.

Use this dashboard as an observer of the existing working application-remediation
path. The Recovery view joins independently collected workflow receipts to the
actual OTel spans already driving Visual flow and Logs. It does not invoke
agents, write to Kubernetes or GitLab, or submit an approval.

Start with [the Kyverno extension](../kyverno-application-specialist/README.md).
Preserve the working ordinary/native kagent adapter, approval ledger, GitLab
project boundaries, and GitOps delivery flow. The old Pi-pane session API and
the OTel bundle's Substrate example are not requirements for this integration.

## Publish recovery evidence from the working observer

The implementation reads two optional files:

- `RECOVERY_PROFILE` names the reviewed profile JSON with the expected incident,
  run, native task, observer, agent, repository, policy, and application identity.
- `RECOVERY_SNAPSHOT` names the current metadata-only observer snapshot JSON.

When configured, both files are required. Each is limited to 64 KiB. The parser
rejects unknown fields, duplicate JSON keys, mismatched identities, invalid
revisions, and unsupported values. See the exact versioned contract in
[`recovery.py`](recovery.py) and its tests. These files contain no credentials,
raw logs, tool arguments/results, model messages, or knowledge document bodies.

The observer is the existing trusted workflow service or a separately reviewed
adapter with its own scoped read access. It reads the actual native tasks,
independent approval ledger, GitLab MR/CI/merge, GitOps objects, deployed policy,
Deployment, and admission/HTTP probes. It publishes complete snapshots with
atomic file replacement. Never let an agent's answer directly set a dashboard
`verified` flag. Reuse the original receipt identities and retain source receipts
privately for independent inspection.

The viewer validates consistency and freshness. It does not authenticate GitLab
or Kubernetes on behalf of a file writer, and it does not establish that an
operator-supplied receipt is authentic. Protect the observer, profile, storage,
and dashboard through the deployment's existing access controls.

If the working adapter uses a post-GitOps follow-up task, pin its actual
`verificationTaskId` in the reviewed profile. The verification receipt records
that task and the primary incident task as `parentTaskId`. Both the receipt and
the referenced native span must match those exact identities. The viewer does
not infer task lineage from a session or a nearby timestamp.

The application can show recovered only after the receipts agree on:

1. The actual fault and native investigation for the selected incident.
2. The exact proposed MR head, passing positive/negative policy tests,
   independent reviewer, and human decision.
3. The real merge SHA, GitOps source and applied revisions, and fresh policy
   content/generation with enforcement retained.
4. Fresh successful valid admission probes and continued denial of the invalid
   fixture.
5. The current application rollout, matching observed generation, desired
   ready/updated/available replicas, and repeated successful HTTP response hashes.
6. A completed native verification task bound to those particular receipts.

If a later probe fails, a required read becomes stale, or a revision changes,
the current state loses green. Historical receipt completion does not establish
current application health. Fixture inputs remain labelled fixture replay and
cannot produce a complete live demonstration result.

## Policy APIs without native observed generation

Keep an absent native policy `observedGeneration` as JSON `null`. A generation
copied from metadata is not controller status. The separate
`stable-read-and-admission-probes` variant requires these extra fields on each
of `liveObject`, `probes`, and `verification`:

```json
{
  "observedGeneration": null,
  "observationMethod": "stable-read-and-admission-probes",
  "activeProbeGeneration": 3
}
```

The example generation is illustrative; use the actual policy generation.
The `probes` receipt also requires `policyReadBefore` and `policyReadAfter`.
Each is the exact metadata-only runtime read object with the snake_case keys
`uid`, `generation`, `policy_spec_sha256`, `ready`, `deleting`, `enforcement`,
and `observed_at`. Both reads must match the live UID, generation and healthy
spec digest, be fresh, Ready, Enforce and nondeleting, and bracket **all** actual
admission observations. The after-read must precede or equal the probe receipt's
`recordedAt`. The same positive/negative probe count, duration, ordering, rollout,
HTTP, native task, and retained native-span gates still apply. A present but
mismatching native observed generation cannot use this variant.

For the scoped runtime adapter's `verify_recovery` output, use this mapping:

| Snapshot field | Actual source |
| --- | --- |
| `liveObject.uid`, `generation`, `policySpecSha256`, `ready`, `deleting`, `enforcement` | The admission receipt's `policy_read_before` keys, translating only `policy_spec_sha256` to `policySpecSha256` |
| `liveObject.recordedAt` | That before-read's actual `observed_at`, retaining the existing before-admission stage ordering |
| The three receipts' `observedGeneration` | `policy.observed_generation`; retain `null` |
| The three receipts' `observationMethod` | `policy_observation_method` |
| The three receipts' `activeProbeGeneration` | `active_probe_generation` |
| `probes.policyReadBefore`, `probes.policyReadAfter` | `policy_read_before`, `policy_read_after`, with their nested snake_case keys unchanged |
| `probes.policySpecSha256` | `policy.policy_spec_sha256`, identical to both admission reads |
| `probes.observations` | Complete recorded admission observations; map `probe_id` to `probeId` and `observed_at` to `observedAt`, retaining `kind` and `result` |
| `probes.recordedAt` | Actual observer recording time after the admission after-read |

Use the real native task API and retained native span for the verification
receipt and its trace/span IDs; the adapter result alone is insufficient.
`current_policy_read_before` and `current_policy_read_after` are later runtime
readbacks around HTTP checks. They do not bracket the earlier admission probes
and must not replace the admission bracket or its timestamps. If actual source
times or bindings do not satisfy the ordered receipt chain, keep recovery
unknown or blocked; do not move timestamps to produce green.

## Join execution telemetry by identity

Reuse the collector and exporters in
[NATIVE-KAGENT-OTEL.md](NATIVE-KAGENT-OTEL.md). Preserve existing export destinations.
The collector sends OTLP HTTP JSON without compression to this viewer's
`/v1/traces` and `/v1/logs`; protobuf exports do not work here.

Propagate the actual W3C trace context through synchronous dispatch, model, and
MCP calls where supported. A GitLab pipeline or GitOps reconciliation may run
in a different trace. Keep its actual trace IDs and explicit receipt references
rather than manufacturing one continuous parent chain or matching by time.
For custom instrumented adapters, propagate `flow.incident.id` and `flow.run.id`
as bounded metadata. Preserve the runtime's actual `a2a.task.id` or
`gen_ai.task.id`, agent identity, tool call ID, and original trace/span IDs.

The snapshot's telemetry references must point to spans actually retained in
the dashboard. Profile-pinned MCP service identities distinguish Kubernetes
and GitLab server execution. Client attempts alone do not prove server execution.
If telemetry is missing or evicted, the execution proof remains incomplete.

Show these distinctions during the demonstration:

| Audience step | Evidence that can light it up |
| --- | --- |
| Classifier admission | Actual bounded classifier decision and accepted native investigation receipt. The new recovery viewer consumes the admitted incident; it does not implement classification. |
| Skills and knowledge | Actual runtime skill/resource reads plus reviewed package/file receipts for exact attribution. A mounted file is insufficient. |
| Model selection | Observed ModelConfig/profile resolution, when instrumented, identifies configuration. A real model-operation span identifies execution and selected model. |
| Model garden/gateway | Actual gateway/provider traffic and model operation. A configured route does not establish a network call to a model-garden service. |
| Kubernetes MCP | Actual server/handler tool execution from the selected backend. |
| GitLab MCP | Actual tool execution, with independent MR/CI/merge readback for resulting effects. |
| GitOps sync | Exact source/applied revision and current object readback. A successful MCP span alone is insufficient. |
| Application green | Fresh policy, rollout, HTTP, and native verification receipts. OTel activity alone is insufficient. |

Use the existing combined Skills and knowledge node for supported runtime
operations. Native Go `load_skill` / `load_skill_resource` and supported ordinary
Python `skills` / `read_file` tools have different telemetry contracts. Inspect
the deployed runtime; do not require a version's tool names on another runtime.

The Recovery view reports application recovery and telemetry completeness
separately. An application may recover while some OTel is missing. That does
not establish a complete observed end-to-end demonstration.

## Mount the observer output in the existing Helm release

The chart's opt-in settings are:

```yaml
recovery:
  enabled: true
  profileConfigMap: '{{REVIEWED_RECOVERY_PROFILE_CONFIGMAP}}'
  snapshotClaim: '{{EXISTING_RECOVERY_OBSERVER_PVC}}'
```

Create the profile ConfigMap through the approved GitOps path with key
`profile.json`. The existing observer writes `recovery.json` to the referenced
PVC. The dashboard mounts the profile at `/recovery-profile` and the PVC at
`/recovery-observer`, both read-only. Enabling recovery also sets
`READ_ONLY_VIEWER=true`. No Kubernetes service-account token is mounted and no
GitLab/model credential is added to the dashboard. These names refer to existing
resources; the chart does not provision the observer, PVC, or its permissions.

Check access modes and scheduling. A read-only PVC mount does not make an RWO
volume multi-node capable. Colocate a suitable observer/dashboard or use the
approved storage mode. Mount the ConfigMap directory, not a `subPath` file, so
that approved profile updates can become visible.

For a workstation rehearsal, set the two file paths and start `backend.py` with
`READ_ONLY_VIEWER=true` and a loopback bind. Publish only explicitly labelled
fixture receipts when live adapters are unavailable. Verify the rendered UI as
well as parser tests before transferring the source. Do not represent a fixture
snapshot as a new live agent execution.

## Prove the actual combined workplace run

Capture one fresh run from fault to verified recovery in the existing interface.
Observe the real classification, task admission, skill/knowledge reads, model
route, MCP execution, repository fix, review/decision, merge, GitOps sync, and
application checks. Keep the view amber while reconciling. Check its final
state against independent source receipts, then capture the dashboard and its
correlated Logs view. Repeat with a failed probe and missing telemetry to show
that neither can masquerade as a complete green proof.

The independent local policy fixture proves only real Kyverno admission and
application behavior. The work agent must supply the live classifier, native
task, repository, approval, GitOps, exporter, and observer integration. This
source change does not claim those workplace stages have run.

References are the official [OTel context propagation guide](https://opentelemetry.io/docs/concepts/context-propagation/),
[OTel trace links](https://opentelemetry.io/docs/specs/otel/trace/api/#link), and
[Flux Kustomization status](https://fluxcd.io/flux/components/kustomize/kustomizations/#last-applied-revision).
