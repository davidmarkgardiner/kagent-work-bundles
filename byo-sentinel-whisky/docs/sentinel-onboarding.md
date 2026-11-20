# Bring Your Own Sentinel with Whisky

The browser rehearsal uses a Whisky stand-in with synthetic Kubernetes status. Use the existing Whisky application and its approved bottle asset for the workplace demo.

## Confirm the workplace contract

| Owner | Confirm before applying an instance |
| --- | --- |
| Platform onboarding | Scanner source revision and image digest from yesterday’s job, installed KRO API and resource schema, generated job and configuration ownership |
| Whisky team | Source repository, demo namespace, workload identity and one reversible demo-only health condition |
| Ingress owner | Authenticated sender identity, bounded report schema, receiving route and correlation receipt |
| GitLab project owner | Approved project ID, issue-write principal, explicit opt-in and label used by the board list |

Review the installed KRO contract and scanner output before preparing the actual instance. Keep deployment-specific names and IDs in the workplace repo. The instance should bind to its own namespace and workload. The job should use a dedicated read-only service account with access only to the Kubernetes fields needed by the agreed checks. Keep report destinations platform-controlled. Verify sender identity against the registered namespace and resolve the GitLab project from an approved binding at the receiver.

## Enable Sentinel through GitOps

1. In the proposed onboarding control, select the application, owning team, and approved worker clusters. Show the namespaces and optional GitLab destination before submission.
2. **Enable Sentinel** submits a proposed change through the existing GitOps review path. Use one reconciler per target. Flux or the existing Sync controller applies the reviewed KRO instance, which manages the scanner resources on the worker.
3. The central inventory records each desired registration from the merged revision, with a stable cluster, namespace and workload binding. Record reconciliation and reporting as separate signals. Start a first-report grace period from the rollout expectation so a failed reconciliation or a Sentinel that never checked in becomes visible.
4. The first accepted report establishes coverage. Subsequent deadlines follow each registration's schedule. Changing the target set or pausing a Sentinel updates the central expectation through GitOps.

| Coverage state | What the agent can say |
| --- | --- |
| Awaiting first report | A desired registration exists and is within its first-report window. |
| Online | A current completion receipt exists, even if it contains an application finding. |
| Overdue | The first-report or recurring deadline elapsed without a current receipt. |
| Paused or retired | The registration is intentionally out of active coverage. |
| Unknown | The inventory or receipt system is unavailable or stale. |

Show online and expected counts together, for example **2 of 3 online**. Require fresh inventory and receipts before reporting **All online**. An empty active inventory should show **No active Sentinels**.

## Run the team demo

1. Open Whisky. Show the Kubernetes information and bottle image. Record the app’s namespace and healthy baseline.
2. Show the reviewed KRO instance for Whisky and its generated scanner job. Record the instance generation, job UID and collector image digest. Begin with GitLab issue creation disabled.
3. Use the approved demo condition, such as one unavailable replica in a disposable Whisky deployment. Run a single scan. Show the resulting condition, workload identity and report correlation ID.
4. Show the agentic-cluster receipt for that same report. Confirm the receiving system is using the authenticated namespace binding and that the report contains only permitted fields.
5. Enable the approved demo project binding and process the finding. Verify the GitLab issue URL and board label in GitLab. Replay the same finding and check that the issue count is still one. Use the project binding, stable workload identity and finding type as the deduplication scope.
6. Restore the demo deployment. Retain the correlated receipts privately and clean up the demo issue and instance according to the owners’ agreement.

## Acceptance receipts

Record the scanner source and digest, KRO instance generation and job UID, received report ID, and GitLab read-back with its issue URL and board label. Capture the no-ticket result with GitLab disabled and the existing issue on replay. If delivery is uncertain, inspect the receiving record and GitLab before retrying. If the pilot must stop, disable the project binding first, then suspend or remove the Whisky-owned instance through its normal delivery path.

## Investigate a missing report

Run a scheduled check on the receiving side of the agentic cluster, independently of the scanner. Derive expected runs from the active Sentinel registration, its schedule and configured time zone. Give each run a deadline that allows for scanner runtime and delivery delay. Accept a correlated completion report for every scheduled run, including healthy scans with zero findings. Keep receiver health visible so an unavailable receipt store does not turn into a fleet of false scanner alerts.

When an active registration is overdue, open one investigation keyed by Sentinel registration and expected run. Give the agent read-only access to the registration, Job status, bounded Kubernetes events and receiver status. Skip intentionally suspended or retired registrations.

| Evidence the agent sees | Handoff |
| --- | --- |
| Expected Job is missing | Check KRO reconciliation and scheduling. Route to the platform owner. |
| Job is pending past its runtime budget or failed | Capture the Job condition and bounded event summary. Route the scanner failure to platform operations. |
| Job succeeded and its report was rejected | Capture the receiver rejection and correlation ID. Route to the ingestion owner. |
| Job succeeded and receipt status is unknown | Inspect delivery and receiver health. Report the evidence gap and keep the investigation open. |
| The receiver accepted a late report, or the next expected run completes successfully | Record the recovery receipt once and close the investigation. |

Keep missing-report investigations on the operational route. App findings still follow the registered GitLab opt-in. The agent reports what it can verify and leaves changes or retries to the normal operating workflow.

Also test a merged registration that never reports and verify the fleet count includes it from day one. During a receiver outage, show coverage as unknown and route one receiver investigation through the operational path.

For acceptance, choose **Sentinel misses its report deadline** in the rehearsal. In the workplace pilot, arrange one missed report on the disposable Whisky Sentinel. Record the expected run, overdue event, linked agent diagnosis, single operations handoff and correlated recovery receipt. Also confirm a healthy zero-finding report and an intentionally suspended Sentinel generate no overdue incident.
