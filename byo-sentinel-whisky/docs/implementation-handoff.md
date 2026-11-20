# Workplace implementation handoff

Start in the workplace repository with the existing Sentinel scanner job and Whisky application. Record the source revision, deployed resource versions, scanner image digest, current delivery route and demo namespace in the workplace evidence record. Resolve any differences between the rehearsal and the actual deployed contracts before writing manifests.

| Work item | Change to prepare | Acceptance |
| --- | --- | --- |
| GitOps onboarding control | Submit one reviewable desired-state change for the selected app and approved worker clusters. Use the existing Flux or Sync reconciler for each target. | Reconcile the reviewed revision and show that repeating the request creates no duplicate registrations. |
| Fleet coverage | Seed expected registrations from merged GitOps desired state. Report desired versus current coverage before adding a Grafana dashboard. | Show an expected target that never checked in, then verify the count reaches all online after recovery. |
| KRO onboarding | Reuse the installed KRO resource definition or extend it through the existing review path. Add the Whisky instance and verify the generated namespace-scoped job and identity. | Match instance generation, Job UID and scanner image digest. |
| Shared and specialist checks | Pair each specialist with the existing generic workload baseline. Keep per-scanner completion receipts and correlate findings in triage. | Show that a generic critical failure and a component-specific failure are both reported. Verify overlapping evidence for the same finding produces one incident. |
| Report delivery | Send bounded evidence to the approved Agent Gateway endpoint. Record the current cap of three alerts a day per application per cluster. Include a completion for healthy runs and correlate each accepted completion with the registered Sentinel and expected run. | Read back a finding and a zero-finding receipt from the receiver. |
| App investigation and GitLab opt-in | Have the agent connect back to the worker cluster and investigate using scoped read-only evidence. Configure the chosen output route, such as GitLab, ServiceNow or an approved endpoint. Bind an owner-approved project and board label at the receiver. Use the cluster-aware incident key below to identify repeat findings. | Verify no issue with opt-in disabled, one labelled issue with opt-in enabled, and the same issue on replay. |
| Missing-report detection | Run the deadline check independently at the receiver. Use the registration schedule and grace period to identify overdue runs while accounting for receiver availability and intentional suspension. | One missing run yields one investigation. A healthy zero-finding report and a suspended instance yield none. |
| Agent investigation | Resolve the registration, expected Job state and receiver records via read-only tools. Route the diagnosis to the responsible operational owner. | Link the overdue event, diagnosis and handoff. Verify an accepted recovery report closes the investigation. |

Use the [KRO scanner profiles](sentinel-profiles.md) for the ExternalDNS and External Secrets candidates and their integration checks.

Use the [pilot runbook](sentinel-onboarding.md) for demo order, evidence capture and cleanup. Keep populated identifiers and receipts in the workplace repository. Present the [browser rehearsal](sentinel/index.html) as sample evidence until the pilot receipts are available.

## Completion and ticket contract

Use the proposed [v1 completion schema](profiles/completion.schema.json) at the Gateway receiver. The sender attaches registration and Job identity to the scanner result. Authenticate the sender and resolve the cluster, namespace, registration and output binding from trusted configuration. Verify the reported Job and schedule against that binding. Use registration UID and scheduled UTC time to count each expected run once, even when a Job is retried. Keep the Job UID as evidence. Accept completions independently of the three-alert escalation budget, including healthy and unknown scans. An unknown completion proves the scanner reported and opens an operational investigation when warranted. It must never mark the application healthy.

For findings, normalize the type and affected resource before routing. Match an open issue using the destination binding, cluster, namespace, resource kind and stable name, and canonical finding type. Match generic and specialist rollout evidence to the same type. Use an atomic reservation on that key before writing an issue. Replays of the original run retain the original delivery outcome. If a fresh finding recurs after closure, open a new incident. A duplicate or a replay consumes no alert allowance. Verify the two-cluster case creates separate issues.

The schema defines the handoff to the existing sender and receiver. The portable Jobs emit scanner results to stdout and still need that integration.
