# Scoped Kyverno recovery runtime

This stdlib Python 3 service is a real-API adapter, not a synthetic incident or
model implementation. Unit tests use explicit fakes and establish only local
logic. Infrastructure, native kagent tasks, native skills, human decisions and
admission dry-runs remain the parent's responsibility.

## Two structures considered

1. A subclass of the earlier rollback service with one mutable JSON state blob
   and a polling thread. This minimizes edits but combines admission, network
   writes and independent approval in the same scattered state flags. A crash
   between branch/commit/MR writes needs more than a merge-attempt flag.
2. A small typed configuration, transactional SQLite ledger, fixed real-API
   adapter and independent admission class. Operation intent is committed before
   a write; an unreturned write becomes unknown and is read back by identity.
   Classifier requests reserve a permanent allowance before calling the supplied
   model callback. There is one outbox identity per run.

Choose 2. This preserves the earlier exact-head merge gates while making the
uncertain write and dispatch cases reviewable. It is a single-process/PVC proof;
it does not establish HA or host-loss recovery.

## Types and signatures (before implementation)

- `Config.from_dict(value) -> Config`: frozen config; canonical hash binds the
  SQLite database to one run and scope. Secrets are file contents, never config.
- `Ledger(path, config_identity)`: WAL, synchronous FULL, transactional state,
  operation journal, admission observations, classification reservations/outbox.
- `Runtime(config, ledger, gitlab=None, kube=None, telemetry=None)`: injectable
  adapters for local tests. Production adapters verify TLS, refuse redirects and
  bound upstream responses. Kubernetes adapter supports only GET.
- Fixed methods `read_kyverno_incident()`, `read_policy_repository()`,
  `propose_policy_fix(reason, image_pattern)`, `inspect_policy_fix()`,
  `merge_policy_fix()`, `verify_recovery()`.
- `Runtime.control(body)`: independent operator receipts only. No generic
  `approved=true` input. A separate request receipt captures actual native
  INPUT_REQUIRED task/approval/tool-call IDs. A human authorization receipt must
  match those IDs, the MR/head, configured human, and native receipt digest.
- `Admission(config, db_path_or_ledger).observe(packet) -> dict`: actual dry-run
  known-good denials plus blocked rollout; three distinct probe IDs in 60..120s.
- `Admission.classify(candidate_id, callback) -> dict`: callback receives a
  bounded untrusted candidate and explicit 512-output-token ceiling, once per
  candidate. The callback must use the approved real classifier route. There is
  no default callback, mock fallback, hidden retry or reset on restart.
- `Admission.dispatch(callback) -> dict`: commit one message ID and pending
  outbox record before callback. Timeout/crash remains unknown.
- `Admission.reconcile_dispatch(receipt) -> dict`: accepts the original message
  ID and actual accepted native task identity; never dispatches a fresh task.

## Operator and MCP boundary

HTTP routes: unauthenticated GET `/healthz`; operator-only GET `/state` and
POST `/control`; role-specific POST `/mcp/investigator` and `/mcp/reviewer`.
Bearer tokens come only from `/config/investigator.token`,
`/config/reviewer.token`, `/config/operator.token`. Reviewer exposes read and
inspect tools only. Investigator has proposal and verification; its merge tool
must additionally be configured with native `requireApproval` by the parent.

Merge checks exact candidate content and single-file diff, unchanged source and
target heads, newest exact-head pipeline, required successful jobs and JUnit
cases, independent reviewer PASS on that same binding, actual native approval
request IDs and separately authenticated human decision. A GitLab SHA
precondition closes the source-head race. A target-head re-read detects drift;
GitLab does not expose a target-SHA merge precondition, so branch protection and
the bounded isolated project are still required for target concurrency.

Native receipts recorded here are authenticated operator attestations of actual
native data, not cryptographically verified kagent assertions. If the deployed
native API cannot supply the needed human principal and approval/tool-call
binding, stop at INPUT_REQUIRED. Do not synthesize approval data.

## Evidence and telemetry

Only exact configured project/file/branch/resource paths are constructed.
Proposal modifies one JSON field from `docker.io/libary/*` to
`docker.io/library/*`; canonical full-file hashes pin both known documents.
No shell, arbitrary SQL, URL, resource, project, apply or delete tool exists.

Positive/negative dry-run probes are supplied as authenticated operator
receipts, never invented by the MCP service. Recovery combines those receipts
with fresh live policy/spec/generation, Flux merge-SHA reads, Deployment rollout
and three actual bounded HTTP status/body-hash observations. Missing proof is
waiting/unknown.

For served Policy APIs that omit observedGeneration, an explicit proof variant
uses actual positive/negative dry-run observations bracketed by identical
Policy UID/generation/spec-hash, Ready/nondeleting Enforce reads. Native
observed_generation remains null. Output names this method and records the
active probe generation and actual brackets; Ready alone never infers status.

Incoming traceparent and tool-call metadata propagate into real MCP SERVER
spans and metadata-only OTLP logs. Configured logical Kubernetes and GitLab
service names identify actual operations. No fabricated model/skill spans or
raw HTTP bodies, denial messages, tokens, headers or logs enter telemetry.
Telemetry export failure is visible in the ledger and never becomes a fake
success. MCP replies are at most 8 KiB; inbound requests at most 64 KiB.

Verified primary API references: [GitLab commit creation](https://docs.gitlab.com/api/commits/)
supports creating the fixed branch in the same commit request with `start_sha`
and per-file `last_commit_id`; [pipeline test reports](https://docs.gitlab.com/api/pipelines/)
provide individual named JUnit case statuses. These source checks do not prove
the installed GitLab instance's behavior.
