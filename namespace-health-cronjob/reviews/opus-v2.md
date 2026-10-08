**Verdict: ACCEPT WITH CONDITIONS**

Reviewer: Claude Opus 5.5 (`claude-opus-5-5`), reviewing only the supplied text with no tools.

The architecture, scope and the four revision-1 corrections hold up. The remaining issues are contract wording that can be fixed in the plan before coding. None needs a new component. Conditions 1–3 should be edited into the plan before implementation starts. The rest are build-time tests.

## Pre-build conditions (plan text edits)

**1. §4 and §3: "deferred required inputs yield `unknown`" conflicts with round-robin sampling.**
- Every run deliberately leaves most containers uninspected, and any container without a matcher is `not-configured`.
- As written, nearly every quiet run becomes `unknown`, and the §6 alert on unknown coverage fires every hour.
- **Smallest fix:** define "required inputs" as two things:
  - essential API state for every watched namespace, and
  - log rotation progressing within a declared cycle no longer than the maximum detection delay.
- Under that definition:
  - containers deferred by rotation are `sampled`;
  - `not-configured` containers are listed but force `unknown` only if policy marks them required.
- Also stop using "deferred" for two meanings. It currently covers both qualifying namespaces that were not selected and inputs that were not inspected.

**2. §5: the payload digest makes every Pod retry a conflict.**
- On a retry, assessment start/end, timestamps and evidence counts all change.
- So "matching replays" only covers transport duplicates, and the conflict alert becomes routine noise.
- **Smallest fix:** add a `finding_digest` over status, selected namespace UIDs, rule IDs and workload references, excluding timestamps and counts.
  - Same finding digest means duplicate.
  - Different finding digest means conflict.
  - Keep the full-payload digest for audit.

**3. §6: the monitor's inputs are not specified.**
- The Sensor drops quiet and unknown records, so the receiver never sees them.
- Receiver conflicts live in an Argo namespace in the source cluster.
- **Smallest fix:** state that the monitor consumes the trial topic directly, keyed by cluster and `slot_id`. Also state that the receiver emits conflict outcomes as a record or metric the monitor can read. If Kafka shares the source failure domain, say so.

## Build-time conditions (tests, not redesign)

**Current state without duration.**
- Rules 100 and 80 correctly keep zero-ready StatefulSets and DaemonSets visible.
- Gap: a partial deficit where Pods are stuck in ImagePullBackOff, CreateContainerConfigError or an init failure is neither CrashLoopBackOff nor Unschedulable. It only reaches rule 60, and only if Events exist.
- The Pod Ready condition's `lastTransitionTime` gives a real duration. Widen rule 90's Pod clause to a named set of waiting reasons.
- Failed Jobs also match no rule; confirm that is intended.

**Noisy, byte-limited tails.**
- Verify whether server-side `limitBytes` truncates from the start of the returned stream. If it does, the newest lines are dropped when `tailLines` × line size exceeds 128 KiB.
- Size `tailLines` so the tail fits within the byte limit, and treat a trailing partial line as truncation evidence.
- Expose the minimum detectable error density per container, roughly 20 ÷ lines inspected.
- The info-flood fixture must state its error ratio, so a pass means detection was actually demonstrated rather than achieved by accident.

**Manual Jobs.**
- `kubectl create job --from=cronjob` sets an ownerReference to the CronJob, so owner verification alone passes. The missing scheduled-timestamp annotation is the real guard.
- Also:
  - reject Jobs annotated `cronjob.kubernetes.io/instantiate: manual`;
  - restrict Job creation in the assessor namespace, since a forged annotation is otherwise in scope;
  - normalize the annotation's offset to UTC before deriving `slot_id`;
  - use Kafka ACLs so canary credentials cannot write the scheduled topic, and scheduled credentials cannot write the canary topic.

**Forbid plus a hung Job.**
- Set Job `activeDeadlineSeconds` to about 180 s.
- Set `startingDeadlineSeconds` well under the receiver's two-hour age bound.
- Together these stop a stuck Job from blocking later slots or emitting reports that are always stale.

**Confirmed consistent:**
- retries reuse the slot;
- quiet and unknown records cannot claim a slot;
- first-valid-investigate semantics;
- 72-hour receipt retention against the two-hour age bound;
- the honest RBAC limits on label-based cleanup.

## Essential evidence before workplace use

- **Preflight receipt:** Kubernetes ≥1.32 annotation present on real scheduled Jobs and absent on `--from` manual Jobs; Argo controller, EventBus and watch scope verified.
- **Acceptance matrix with raw outputs:** a retry with unchanged findings is classified as a duplicate, and a retry with changed findings raises a conflict alarm that the external monitor actually receives.
- **Benchmark:** 20 report-only runs against the ceilings, including per-container inspected time span and detection density under the flood fixture.
- **Real-clock soak:** at least three hourly transitions correlated from scheduled timestamp to Kafka offset to receipt, plus a missing-slot alarm demonstrated with the assessor suspended.
- **Isolation:** original routes unchanged against the baseline, and rollback rehearsed.
- **Workplace:** separate preflight of versions, Kafka ACLs and Argo topology, then a workplace canary. Home-lab results do not transfer automatically.
