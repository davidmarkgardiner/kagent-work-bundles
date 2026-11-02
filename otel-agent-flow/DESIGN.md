# Recovery observer design

The recovery evidence panel is a read-only view in the existing OTel dashboard. Live integration is
pending the workplace adapter contract. No cluster, agent, GitLab or model action
is implemented or claimed by this change.

Two distinct alternatives were considered:

1. **Mounted snapshot:** an independently authenticated observer reads the
   existing incident, approval, GitLab, GitOps, Kubernetes and native-task sources,
   then atomically replaces a bounded JSON file. The dashboard validates that
   file against a separately reviewed, read-only profile. This introduces no
   network ingestion or execution authority.
2. **Authenticated event ingestion:** adapters submit authenticated events to a
   durable ledger; an event reducer owns ordering, deduplication and transitions.
   This would support independent sources and history, but needs credentials,
   durable storage, replay controls and an approved adapter contract.

The mounted snapshot is chosen for this bounded observer increment. The
projection checks consistency, **not authenticity**. File access, observer
authentication, human identity and complete probe reporting remain the external
observer's responsibility. A forged, internally consistent file is not detected
cryptographically. Neither the profile nor the snapshot is an agent output.

## Named data shapes and reducer

`RecoveryProfileV1` pins one incident/run/task and target, one authenticated
observer identity, approved reviewer and human approver identities, one exact
repository policy path and healthy policy-spec hash, agent identity, MCP service
identities, live/fixture mode and a 30..300 second freshness ceiling.

`RecoverySnapshotV1` repeats the binding and observer identity, capture time,
bounded fault/fix summaries, optional typed stage receipts and exact trace/span
references. Every receipt repeats the complete binding. Unknown fields, duplicate
JSON keys, invalid identifiers or hashes, control characters, and files exceeding
64 KiB are rejected. Raw logs, prompts, arguments and tool results have no fields.

`RecoveryView` is the reducer output: `unknown`, `blocked`, `recovered`, or
`replay-passed`, plus stage reasons, bounded display metadata and separately
derived telemetry checks. Missing receipts, unreadable files, stale/future data,
or absent native verification telemetry can never yield live recovery. Historical
CI and approval do not expire by themselves, but fresh live readback and probes
are mandatory. A later failed valid probe or admitted invalid probe removes
recovery. Fixture mode can only say **Fixture replay passed**.

The ordered gates are fault → investigation → proposal → exact-head CI →
independent review → human approval → merge → GitOps → live policy → admission probes
→ application recovery → native verification. SHA relationships and receipt times are checked across
the chain. At least three distinct valid admissions must span at least
60 seconds within 120 seconds, followed by a retained invalid-probe denial. All
reported recovery probes must be fresh, after live readback, and still succeed
in their expected direction. The fixed healthy spec hash and `Enforce` readback
prevent this viewer from accepting an unreviewed policy body or Audit result.

The fault also requires an observed blocked rollout for the pinned application
Deployment. A policy dry-run with already running healthy pods is insufficient.
The profile pins application namespace, Deployment name, HTTP success status and
expected response-body SHA-256. The application receipt must read back the same
UID, a current generation, desired replicas greater than zero, total/updated/
ready/available replicas all equal to desired and zero unavailable replicas.
Three fresh HTTP status/digest observations must span 60..120 seconds after that
rollout readback. No response body or URL is retained. A later failed HTTP result,
old serving replica, replaced Deployment, or incomplete rollout blocks recovery.
The response digest is SHA-256 of the exact returned bytes, including a trailing
newline. No decoding, whitespace trimming or JSON reserialization is permitted.

The verification receipt comes from the native task API and binds its completed
result to the merge SHA, probe receipt, live policy generation, application
receipt, application UID and application generation. Its referenced span
must actually exist in the retained ActivityStore snapshot and match the pinned
native agent/task. The observer supplies provenance; the viewer never equates
an ended OTel span with task completion.

Version 1 defaults verification to the primary investigation task. A separately
reviewed optional profile `verificationTaskId` pins an explicit follow-up task.
The verification receipt must include `taskId` matching that pin (or the primary
task by default), and `parentTaskId` matching the primary binding. Its exact
native span must carry the verification task ID. Other execution references
remain bound to the primary task; the viewer never guesses lineage from timing.
The referenced verification span must end after the application and admission
observations, so an earlier task span cannot stand in for final verification.

Every displayed telemetry reference joins by exact trace/span ID and a native
task anchor, or explicit incident/run/task metadata on a separate backend trace.
Conflicting task/incident/run metadata invalidates the join. The full demo also
needs actual model, gateway, skill, knowledge, Kubernetes MCP and GitLab MCP execution
spans. No synthetic spans, time matching or inferred package reads are created.
These checks describe observed operations, not actual knowledge-file bytes.
`completeDemoProof` covers this receipt-based recovery and its referenced
execution evidence only. It does not validate classification, incident admission,
durable dispatch or the full critical-only classifier implementation.

## Files and atomic-writer contract

Set `RECOVERY_SNAPSHOT=/observer/recovery.json` and
`RECOVERY_PROFILE=/recovery-profile/profile.json`. With neither configured,
the original dashboard continues to work. With either missing, health is unknown.
Mount both read-only in the dashboard. Use a distinct externally authenticated
observer and one writer; write a temporary file on the same filesystem, flush it,
then rename it over the snapshot. Publish a complete current snapshot, including
any later probe failure, and refresh live readback/probes before they expire.
Do not refresh `capturedAt` alone to reuse old evidence. Do not truncate the
mounted file in place or put credentials/private endpoints into metadata.

`recovery.py` owns the strict shape and reducer. Its tests define complete example
documents, malformed/mismatched cases, freshness and OTel joins. Fixtures under
`evidence/recovery-fixture-*.json` are permanently labelled fixture mode and
contain no claimed runtime execution. Use a separate live profile for real proof.

Every receipt has exactly `receiptId`, `binding`, `recordedAt`, its stage's
fields listed in `recovery.FIELDS`, and any stage-specific optional fields in
`recovery.OPTIONAL_FIELDS`. Receipt IDs and probe IDs are distinct within
their respective document/window; all times are integer UTC epoch seconds.
Git SHAs are full lowercase 40- or 64-character hex, without branch/ref prefixes.
Spec and body digests are lowercase 64-character SHA-256. The observer must
compare the reviewed canonical healthy policy spec with a freshly read live
spec; hash `json.dumps(spec, sort_keys=True, separators=(',', ':'),
ensure_ascii=True, allow_nan=False).encode('utf-8')` consistently in both places.

For policy APIs without native observed generation, the explicit
`stable-read-and-admission-probes` variant keeps that field null in the live,
probe and verification receipts. Each carries the same method and actual active
probe generation. Two fresh metadata-only policy reads on the probe receipt
must bracket every admission observation and match the same UID, generation,
healthy spec, Ready, nondeleting Enforce state. This is active-admission proof,
not inferred controller status. It cannot override a present mismatching native
generation, relax application generation checks, or supply native telemetry.
The exact adapter-to-snapshot mapping is in [KYVERNO-RECOVERY.md](KYVERNO-RECOVERY.md#policy-apis-without-native-observed-generation).

The fault `application` object is a blocked Deployment readback, and the recovery
`application` receipt is the completed Deployment readback plus `httpObservations`.
The former is not a healthy baseline. Each admission observation has exactly
`probeId`, `observedAt`, `kind` (`valid`/`invalid`) and `result`
(`admitted`/`denied`/`error`). Each HTTP observation has exactly `probeId`,
`observedAt`, `statusCode` (0 for a transport failure) and `bodySha256` (the
observed digest, or an explicit nonmatching digest on an empty/error response).
Both windows contain at most 16 observations in time order. A failed HTTP probe
must remain visible in the published window; refreshing capture time cannot
erase a failure while retaining earlier success claims.

For offline browser review, generate a fresh, permanently fixture-labelled
profile and snapshot (no OTel is generated):

```sh
python3 -B test_recovery.py --write-fixture /tmp/recovery-review
READ_ONLY_VIEWER=true \
  RECOVERY_PROFILE=/tmp/recovery-review/recovery-fixture-profile.json \
  RECOVERY_SNAPSHOT=/tmp/recovery-review/recovery-fixture-snapshot.json \
  PORT=8791 python3 -B backend.py
```

Open `http://127.0.0.1:8791/#recovery`. Expect **Fixture replay passed** in purple,
12 receipt stages, and unknown runtime evidence. Visual flow and Logs continue
to work. The fixture expires after about 210 seconds; re-export it to review
again. Do not ingest fabricated spans to light up the map.

## Throughput and ownership checklist

- Prerequisite: strict metadata schema and privacy boundary agreed before edits.
- Single owner: this candidate owns recovery code, backend integration and UI.
- Isolation: all edits stay in the unique candidate bundle; no main checkout edit.
- Smallest increment: observer-only state and one tab; no event service or RBAC.
- Verification: reducer behavior, real HTTP state, package imports and existing
  UI tests; parent performs rendered browser inspection. No runtime claim follows
  from these offline checks.

## Demo flow evidence

The operator Demo view embeds the existing purple component topology and a fixed
nine-stage workflow rail. The bridge in the connected Kyverno bundle owns Start
and exact-head dashboard approval. Ordinary viewer routes remain read-only.

`demo.flow` projects only the current run and exact native task identities. Its
scope contains retained trace IDs and a separate selected span-ID set per trace.
Demo evidence cards use that selected set, including causal spans beyond the
bounded event feed. Manual trace inspection is explicitly labelled and can show
the entire selected trace.

Workflow receipts determine passed and blocked stages. Actual recent OTel arrival
determines activity highlighting. A first snapshot never pulses. Coordinator
records highlight only their owned caller operation; native model, gateway,
skills/resource and MCP evidence requires received execution spans. Legacy log
arrival measured at the bridge uses `viewerReceivedAt`, never collector receipt
time. The server exposes both arrival times separately. A closed span cannot
resolve an incident; verified issue closure and the closed workflow phase are
both required.

Older deployed receivers may omit coordinator run attributes. The connected
bridge can correlate a legacy record using an actual persisted caller context
for a recorded operation, with exact run, step, trace, span and start-time checks.
It never inserts missing attributes into received OTel.

A received MCP server span with an unexported transport parent can be associated
with a native task only through the same trace, exact fixed service/tool mapping
and one uniquely enclosing selected native tool interval. Conflicting identity,
ambiguous clients, malformed IDs and out-of-window records remain excluded.
The observation and derived edge identify this as interval inference. Following
Demo uses these verified scope edges for pulses; manual trace inspection uses
the original trace edges. Display correlation cannot authorize execution or
prove application recovery.
