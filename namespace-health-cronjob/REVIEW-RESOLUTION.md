# Independent review disposition

Revision 1 was reviewed independently through Claude Code Opus and Kimi Code.
Both received the same supplied plan text and neither performed live verification.
Original responses and exact input/output hashes are in [reviews/](reviews/).

- **Opus:** actual response metadata identifies `claude-opus-5-5`; verdict
  REVISE BEFORE BUILD, with narrow changes and support for the architecture.
- **Kimi:** requested configured alias `kimi-code/k3`; response stream does not
  independently identify the backend version. Verdict ACCEPT WITH CONDITIONS.
  An initial CLI invocation rejected incompatible flags before model execution;
  the corrected invocation completed. This was not a failed model review.

## Decisions applied to revision 2

| Review finding | Disposition |
|---|---|
| Both: durations cannot be inferred from one snapshot | Name exact condition timestamps. Current critical impact is immediate; non-critical zero-ready controllers without duration evidence use an explicit lower-tier rule after startup grace. No inferred continuous outage. |
| Both: five-minute log-span rule misses chatty containers | Remove the span gate. Twenty recognized recent errors are an observed lower bound. Record earliest/latest inspected time, truncation and matcher coverage; test a tail spanning less than five minutes. |
| Both: simplify log collection | Defer retained-store adapter. Sample workload/application-container identities, reserve a rotation pool regardless of readiness, declare sidecar exclusions and unconfigured matchers, and use deterministic round-robin sampling with a visible coverage cycle. |
| Opus: unknown/quiet silence | Publish a bounded status every completed run; only investigate starts the receipt workflow. Heartbeats do not replace a working external freshness monitor. |
| Opus: scheduled/manual slot collision | Require Kubernetes 1.32+ scheduled-timestamp annotation; refuse missing annotations on the scheduled route. Key by occurrence timestamp, not rounded hour. Manual canaries use an isolated route. |
| Opus: critical workload declaration | Protected policy allowlist identifies exact critical controllers. Tenant-controlled labels cannot silently change priority. |
| Kimi: conflicting retry may contain worse evidence | Retain first-valid-investigate semantics; explicitly describe the delay and require a tested conflict alert. Quiet/unknown status messages do not claim investigation slots. |
| Kimi: Argo namespace/EventBus assumptions | Verify installation/watch scope and EventBus placement before rendering or deploying the trial. No assumed cross-namespace EventBus reuse. |
| Both: external freshness dependency | A named monitor outside the source failure domain and demonstrated alarms are required for soak/production readiness. Absence remains a reported gap. |
| Opus: unnecessary resource reads/concurrency | Remove PVC/CronJob-object reads; begin sequentially and measure before adding parallelism. Do not treat the reviewer's latency estimates as measurements. |
| Opus: namespace UID RBAC | Explicit get-only ClusterRole restricted by namespace resourceNames. |
| Opus: selection cap untested | Use five fixture namespaces to prove three selected and two deferred. |
| Opus: Event history and bus delivery | Use one Events API, latest valid observation time and explicit cumulative-count semantics; include EventBus outage in end-to-end tests. |

## Reviewer recommendations requiring correction or judgment

- Kimi suggested demoting all missing-duration evidence to context, while Opus
  identified that doing so can hide genuine zero-ready StatefulSet/DaemonSet
  failures. Revision 2 uses a separately named current-impact rule with unknown
  duration. Its potential to flag a disruptive rollout is an explicit calibration
  tradeoff, not an assertion that persistence is known.
- Opus suggested that every-run status removes the external-freshness dependency.
  It does not: some observer must notice absence. The monitor remains required.
- Opus described deletion restricted by label in receiver RBAC. Kubernetes RBAC
  does not enforce label-based delete restrictions. Namespace isolation enforces
  the security boundary; cleanup code applies and tests owned-label filtering.
- The score stays named `risk_score` to match the requested threshold workflow,
  but it is explicitly an ordinal maximum of rule tiers. It is not a probability,
  percentage of unhealthy resources or additive count.
- A fallback derived from CronJob-generated names is not used. Requiring the
  documented scheduled timestamp is smaller and easier to prove; older clusters
  need a separately reviewed compatibility change.

## Second-round verdicts and final conditions

Both [Opus](reviews/opus-v2.md) and [Kimi](reviews/kimi-v2.md) returned
**ACCEPT WITH CONDITIONS** on revision 2. Both said the architecture is ready
for the home-lab implementation sequence after narrow contract clarifications.
Their reviews are of the supplied design, not source implementation or live tests.

Revision 3 applies those conditions:

| Condition | Final disposition |
|---|---|
| Opus: planned sampling must not alarm as unknown every hour | Define required per-run inputs; planned rotation is sampled. Missing required matchers/reads and unexpected exhaustion are unknown. Separate omitted qualifying namespaces from uninspected log candidates. |
| Opus: changing timestamps/counts should not make every retry a conflict | Introduce a canonical finding digest separate from the full audit digest. Same findings are duplicates; changed rule/tier/workload identity is a material conflict. |
| Both: monitor cannot observe Sensor-filtered status records | Specify direct status-topic consumption by an external read-only consumer and a conflict alert over collected receipt-workflow outcomes. Verify the actual integration before soak. |
| Kimi: receipt cleanup/replay dependency | Make the 72-hour retention > two-hour accepted-age invariant explicit and test it. |
| Kimi: sampling wording mismatch | Correct the disposition table to reserve rotation regardless of Pod readiness. |
| Opus: partial image/init failures and failed Jobs | Name blocking waiting/init states under the verified Ready=False age rule; add a recent terminal Job failure rule and tests. |
| Opus: manual slots and hung Jobs | Normalize UTC; reject the manual annotation; segregate canary topic ACLs; name the platform-owned Job trust boundary; add 300-second start and 180-second active deadlines. |
| Opus: byte-limited log visibility | Test server slicing direction, record actual inspected density/span and declare the flood fixture's error ratio. |

Revision 3 is the author's reconciliation of the reviewers' conditions, not a
third independently reviewed revision. The original reviewed revisions and hashes
are preserved for comparison. None of these verdicts is an implementation or
workplace certification.

## Remaining execution gates

The home-lab control-plane and worker VMs are stopped. Start them and perform the
fresh runtime preflight at the build stage. The external status/conflict observer
must be identified and demonstrated before the soak; if unavailable, report that
gate as incomplete rather than marking the solution ready. All behavior, resource,
Kafka/Argo, real-clock and workplace-canary evidence in [PLAN.md](PLAN.md) remains
to be produced. No implementation, cluster change or power-state change occurred
during this planning and review task.
