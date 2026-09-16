# Accelerated homelab execution receipt

Run ID: `cluster-health-accelerated-20260915`  
Plan revision: 3  
Executed: 2026-09-15, completed at 20:21 UTC  
Topology: one home-lab worker API server (`red`) and one newly created agent-cage kind API server (`kind-agent-cage-health`) on the same Docker Desktop host  
Mode: report-only; deterministic evidence-only; external delivery disabled

## Outcome

The lab MVP is operational from worker observation through one central summary record:

```text
worker API -> immutable bounded snapshot -> independent HTTPS publisher
-> authenticated cage intake -> PostgreSQL latest-complete state
-> zero-tool deterministic assessment -> one stable local summary key
```

There is no cross-cluster filesystem. The worker does not hold cage database credentials. Cage assessor and reconciler pods have `automountServiceAccountToken: false`. The public manifests contain placeholders; runtime CA, HMAC, TLS, database, and client tokens were generated outside the repository.

## Live state at the final receipt

- Worker snapshot sequence 33: score 65/100, complete coverage, gate active, three grouped problems, 5,062 serialized bytes.
- The cage stored the same sequence 33 and checksum `sha256:b6baff08835174ca0e52c00e21b3ab06f661e060d7eb7f43b9b982f604736a74` within 24 seconds of the worker receipt.
- The latest deterministic assessment recorded score 65, three degraded priorities, zero tool calls, and `model_invoked=false`.
- The single summary ledger contained exactly one open key, `cluster-health/homelab-worker-red`, at revision 3 after later snapshots updated the same record.
- Intake Deployment and PostgreSQL StatefulSet each had one ready replica. The assessor CronJob was active; the external summary reconciler CronJob remained suspended.
- Final locally built intake image ID: `sha256:622eaf2cf4d15e7ce0bc9168f6998032dc35ec0ad27f345a5a8897cad9ddf2a3`.

The observed problem groups were one unavailable/pending kagent Deployment represented as availability and scheduling symptoms, plus selected kube-apiserver error-log evidence. Metrics API and node pod-capacity checks were explicitly unavailable; they were not reported healthy.

## Verification results

`verify-all.sh red kind-agent-cage-health` passed:

- 23 B1 unit/policy tests, including all 1,024 five-domain combinations and 20,000 observations collapsing to one stable workload/symptom identity.
- Two B3 evidence-contract tests and one B4 summary-contract test.
- Go build tests, all five Kustomize renders, worker/cage server dry-runs, publisher RBAC denial checks, and strict public-safety scan.
- Accelerated replay of 20 unique morning/evening slot IDs across ten weekdays, a weekend, and the Europe/London DST change. The replay explicitly reports `substitutes_for_real_elapsed_soak=false`.

Live boundary drills produced these results:

| Drill | Result |
|---|---|
| First worker-to-cage snapshot | Accepted with matching sequence/checksum and complete coverage |
| Missing HMAC signature | HTTP 401 |
| Valid signature with untrusted cluster header | HTTP 403 |
| Same generation/sequence with changed checksum | HTTP 409 |
| 257 KiB body | HTTP 413 |
| Identical signed replay | HTTP 200 with `duplicate=true` |
| Newer partial snapshot | Stored as an attempt; did not replace sequence 32 as the latest complete snapshot |
| Intake scaled to zero | Publisher Job failed after bounded retries; worker snapshot sequence advanced independently |
| Intake restored | Latest worker snapshot converged on the next publication |
| Latest-state row deliberately removed | Identical current snapshot recreated sequence 32 from the retained attempt |
| Summary replay | `created` then `unchanged`; exactly one row at revision 1 |
| New snapshot summary | `updated` the same issue key; no second row |
| Human-closed simulation | HTTP 409 and no replacement; test row restored to open afterward |

The deliberately future-sequenced partial attempt used for the non-replacement drill was removed afterward so it cannot conflict with a real future collector sequence. Temporary certificate, credential, and probe files were also removed; runtime values remain only in Kubernetes Secrets.

The empty PostgreSQL volume was recreated once during bootstrap after a trailing newline in the generated username caused an unusable initial role. No retained assessment data existed at that point. The Secret creation was corrected to literal username/database values before evidence collection.

## Architecture deviation

The reviewed plan proposed a compacted Kafka state lane. To finish the homelab MVP promptly, B2 uses bounded direct HTTPS with a private CA, HMAC authentication, cluster/generation binding, and PostgreSQL. This proves distinct Kubernetes API servers, current-state convergence, and the no-shared-filesystem design. It does not prove Kafka ACLs, advertised broker reachability, consumer groups, compaction, or multi-host failure isolation. The workplace may retain HTTPS or replace it with the approved Kafka lane after environment discovery.

## Deliberate non-claims and open promotion gates

- Ten real working days and a real weekend have not elapsed. False-positive rate, reliability, and SRE usefulness still require real labelled operation.
- At the time of this receipt, the cage had no installed kagent runtime or reachable approved model route. A later temporary model-route proof succeeded under the tightened evidence contract; see [the model receipt](2026-09-15-model-proof.md). A deployed kagent Agent and SRE value measurement remain open.
- The summary is a local PostgreSQL ledger. No GitLab API was called, no issue was created, and GitLab labels/pagination/ambiguous writes are untested.
- The two clusters share one physical Docker host. A second real worker and independent infrastructure failure domain are untested.
- The outage drill was accelerated rather than 30 minutes. It proves decoupling and recovery behavior, not long-duration resource stability.
- Follow-up independent critique, workplace discovery, named SRE acceptance, and staffed-hours rollout remain required.

These are promotion constraints, not hidden implementation work. The running lab path remains report-only and cannot create external tickets.
