# Transfer the proven assessment to the workplace

Revision 3. The accelerated B1–B4 homelab MVP is running through a local summary ledger; this remains a future workplace checklist. No workplace discovery, deployment, model Agent, or GitLab ticket operation has been performed.

## Transfer only the achieved build scope

B1 is a worker-local deterministic report. B2 adds snapshot transport and central assessment. B3 optionally explains supplied evidence with a tool-free agent. B4 maintains a bounded cluster summary issue. Record which builds actually passed before claiming a portable solution.

Transfer exact tested images, snapshot schemas, rule versions, monitor patches, and store migrations through reviewed environment overlays. A workplace-required code change becomes a new tested revision. Include dependencies, licence review, RBAC, fixtures, verifiers, runbooks, and achieved evidence. No `latest` images or implicit broker/database prerequisites for B1.

If the workplace initially has one cluster, deploy the worker and manager roles into separate platform namespaces using the [single-cluster overlay](single-cluster/README.md). Record that this proves logical isolation only. Do not claim independent API-server, network, or failure-domain isolation until the manager components move to a separate cluster.

## Map configuration privately

| Configuration | Public placeholder | Required workplace evidence |
|---|---|---|
| Worker and agentic clusters | `{{WORKER_CLUSTER_ID}}`, `{{AGENTIC_CLUSTER_ID}}` | Explicit identities and achieved topology |
| Platform namespace and monitored tenants | `{{PLATFORM_NAMESPACE}}`, `{{NAMESPACE_ALLOWLIST}}` | Tenant admins cannot access collector state, exec, or producer credential; cross-namespace reads scoped |
| Collection ownership | `{{CERTIFICATION_TEMPLATE}}`, `{{SCHEDULER_OWNER}}` | Actual `aks-certification` version/digest and one scheduler per family |
| Kafka from B2 | `{{KAFKA_BOOTSTRAP}}`, `{{STATE_TOPIC}}`, `{{CONSUMER_GROUP}}` | TLS/authentication, advertised-broker reachability, ACLs, compaction policy, and complete consumer inventory |
| Source binding | `{{PRODUCER_IDENTITY_REFERENCE}}` | Topic-to-cluster and producer-to-namespace allowlist enforcement |
| Central storage from B2 | `{{STATE_DATABASE_REFERENCE}}` | Atomic snapshot replacement, TLS/authentication, backup, baseline/history restore, and schema roles |
| Monitoring and reports | `{{LOG_DATASOURCE}}`, `{{METRIC_DATASOURCE}}` | Real coverage, retention, expected reporting slots, and query scope |
| Optional B3 agent | `{{EVIDENCE_ONLY_AGENT_ROUTE}}`, `{{MODEL_CONFIG}}` | Effective zero tools/delegations and no Kubernetes API access; measured usefulness |
| B4 GitLab | `{{SANDBOX_PROJECT_ID}}`, `{{WRITER_CREDENTIAL_REFERENCE}}` | Exact label filtering, all-state pagination, permission visibility, and ambiguous-write reconciliation |
| Operator and evidence | `{{SRE_OWNER}}`, `{{ALERT_ROUTE}}`, `{{PRIVATE_EVIDENCE_STORE}}` | Rota, acknowledgement/escalation, retention, and redaction policy |
| Delivery | `{{GITOPS_PATH}}`, `{{REGISTRY}}` | Existing object ownership, digest pinning, overlay render, and rollback |

Use existing secret-management paths. Public artifacts contain references only, never real tokens, endpoints, private IPs, subscription IDs, or organisation identifiers.

## Inspect the workplace before rollout

1. Inspect current triage producers, every consumer of `k8s.namespace.findings` or its workplace equivalent, Kafka groups, Sensors, queued workflows, and writers. Identify any consumer trusting `ai_triage_required`.
2. Investigate the reported flood with sampled evidence. Count distinct incidents versus retries/churn/hygiene noise; do not assume the colleague's monitor caused it.
3. Inventory the deployed `aks-certification`, its image, and its check/schedule ownership. Separate active probes, secret inspection, and provisioning from routine passive collection.
4. Verify tenant permissions and credential placement. Run namespace and cluster spoofing denials. A cluster-topic ACL alone does not prevent cross-namespace impersonation.
5. Use B1 measurements to select per-namespace processes or a sharded collector for the target fleet. Re-measure against workplace API throttling, log volume, and resource limits.
6. Confirm topic-per-cluster governance or review an alternative authenticated ingress with equivalent identity binding. Never infer authenticated identity from an untrusted payload field.
7. Identify AKS/CNI-specific gaps, including subnet capacity, managed control-plane visibility, and node-pool constraints. Mark unavailable checks honestly.
8. Inspect old backlog before enabling B2. Coalesce historical snapshots with side effects disabled. Existing delta queues need their own reviewed handling; do not silently reset offsets or delete queued work.
9. Decide state/incident lane coexistence. Summary issues link existing incident tickets; they do not replace the old writer's noise controls. If those controls are unproven, keep the health lane report-only until scope is explicitly agreed.

## Roll out in stages during staffed hours

1. Start B1 on one approved non-production worker with a small namespace allowlist, report-only mode, and platform-owned collector identities.
2. Calibrate for at least 10 working days spanning a real weekend and 20 labelled weekday report slots. Measure per-rule false positives, missed incidents, incomplete coverage, API cost, and operator time.
3. Add B2 only after the local report is useful. Verify actual current-snapshot transfer, source/tenant isolation, broker outage, sequence generation, truncation, and restore behaviour.
4. Add B3 only if its measured explanation value is worthwhile. Verify the effective Agent has zero tools, including indirect sub-agent tools. The existing sentinel orchestrator is not the deployment target.
5. Enable B4 in an approved sandbox during staffed hours. Verify one real summary and its updates, exact-label recovery after lost mapping, reserved evening delivery, and limits under failure.
6. Enable coexistence only after the old incident route passes its own controls. For one crash loop, expect at most one incident issue plus one summary linking it. Keep one-total-ticket mode report-only on the health side unless the other writer is explicitly disabled.
7. Expand scope through reviewed GitOps changes with new capacity measurements. A healthy display score does not authorise ticketing or expansion.

## Operate and recover

Expose last complete snapshot and latest attempted scan separately, including original observation ages. Monitor expected sources, exclusions, partial/pruned observations, publisher supersession/failure, catch-up status, database errors, material assessment changes, request budgets, and writer operations. Preserve local report availability during central outages.

The morning owner reviews current problems and missing evidence. The evening owner checks overnight coverage and blocked updates. Keep system-health alerts monitored throughout calibration and weekends; report-only is not an unattended-service exemption.

Scheduled updates have dedicated morning/evening slots. Unscheduled changes cannot spend them. Reports show suppressed updates and newly blocked incidents at the top. If a human closes a summary and a new fault appears within the create window, retain the report and operational alert and request reconciliation. Do not silently create a replacement or automatically reopen a human-closed issue.

For rollback, disable model and writer dispatch first, preserve snapshots/mappings/budgets, and revert through GitOps. After database restore, coalesce to fresh state with side effects paused. Reconcile exact GitLab cluster/incident labels and operation history; unknown recent spend is treated as consumed. Restore accepted baseline/history separately. A new healthy snapshot is not evidence that ticket mappings are safe.

For ambiguous GitLab outcomes, use exact labels with all states, full pagination, and returned-label equality. Missing labels, inaccessible issues, or multiple candidates block automatic create. Never convert a failed lookup into a new issue without reconciliation. Backlog bulk-closure/deletion remains a separate task.

## Workplace acceptance record

| Acceptance | Required evidence | Status |
|---|---|---|
| Portable scope matches lab | Build gates, image/schema/rule/patch comparison | LAB PACKAGE BUILT; WORK COMPARISON NOT RUN |
| Local report useful | Labelled calibration set and SRE acceptance | LAB REPORT RUNNING; ACCELERATED REPLAY PASS; REAL CALIBRATION NOT COMPLETE |
| Transport and tenancy valid | Fresh snapshot and denied wrong-cluster/namespace tests | LAB HTTPS IDENTITY TEST PASS; WORKPLACE/KAFKA NOT RUN |
| Snapshot recovery correct | Outage/restore/top-N/partial/catch-up cases | LAB OUTAGE/PARTIAL/RESTORE PASS; LONG OUTAGE/CATCH-UP NOT RUN |
| Optional agent adds value | Zero tool calls, supported claims, reviewer time comparison | MODEL HARNESS/CLAIM GUARD PASS; KAGENT DEPLOYMENT AND SRE VALUE TEST NOT RUN |
| Summary delivery bounded | Real issue reuse, labels, reserved slots, coexistence count | LOCAL SINGLE-ROW LEDGER PASS; GITLAB NOT RUN |
| Operator can recover | Missing-report, ambiguous write, restore, and rollback drills | NOT RUN |
| Workplace rollout accepted | Named owner and achieved scope | PENDING |

Until these receipts exist, describe the result only as lab-proven within its recorded build, topology, and test limits.
