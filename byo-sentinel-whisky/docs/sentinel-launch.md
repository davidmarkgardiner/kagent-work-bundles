# Sentinel

**Give your agent a signal from every app.**

This product demonstration simulates the Gateway, agent investigation and delivery path. The lab evidence covers the KRO-generated scanner Jobs.

![A hovering inspection probe scans server racks and relays results to a distant carrier](sentinel/probe.jpg)

An application team selects its app and target clusters and clicks **Enable Sentinel**. The proposed onboarding control prepares a GitOps change for review. Once merged, the existing Flux or Sync reconciler applies the KRO registration on each selected worker cluster. The scanner job gathers Kubernetes health evidence in the worker cluster and sends qualified alerts to its configured Agent Gateway endpoint. The agent connects back to the affected cluster, inspects the workload with scoped tools, and can route the investigation to GitLab, ServiceNow, or another configured endpoint.

[Open the launch and Whisky rehearsal](sentinel/index.html) · [Workplace onboarding and demo runbook](sentinel-onboarding.md)

## Team launch copy

> Meet Sentinel, an application health signal for Kubernetes. Deploy it alongside your app. When Sentinel spots a problem, it reports through Agent Gateway and the agent goes back to the affected cluster to investigate. The result can go to your GitLab board, ServiceNow, or another endpoint your team uses.

## Current scanner, as described by the owner

The current Python scanner sends up to **three alerts per day, per application, per cluster**. The cap bounds agent investigations and downstream issue volume. In the demo, Whisky has one unavailable replica. Step through the Gateway receipt, the agent’s read-only investigation in the worker cluster, and the destination of your choice.

LGTM remains a source of logs, metrics and traces. Sentinel gives teams a direct application-level route from a detected problem to an agent investigation.

## What comes next

A Java classification model is planned to run alongside the application, evaluate signals locally as they arrive, and escalate when a configured threshold is crossed. The current scanner’s detection time follows its scan cadence. The future classifier is the intended path to evaluating signals in real time.

## Generic and specialist checks

Every onboarded workload gets the generic health scan, including specialist targets. The baseline covers critical Kubernetes signals such as unavailable replicas, failed rollouts, crashes, scheduling failures and image pull errors where the workload and approved permissions support those checks. A specialist adds checks for its component, such as an ExternalSecret failing to sync or a certificate failing to renew.

## Fleet coverage

Start with the expected app and cluster pairs from reviewed GitOps desired state. The first accepted completion confirms that a Sentinel is online. A central fleet summary shows every expected registration, including ones that have never checked in. “All online” means every active expected Sentinel has a current accepted receipt. Application health is tracked separately: an online Sentinel can still report a broken app.

Launch with Whisky on one approved worker cluster, then expand by application and cluster cohort after checking rollout and reporting capacity. A later Grafana dashboard can display the same expected inventory, reporting freshness and open investigations.

## When Sentinel goes quiet

A receiver-side check watches for every expected completion, even when the scan finds nothing. If a Sentinel misses its deadline, an agent checks the KRO registration, scanner Job and receiving records, then routes the diagnosis to the operator who can act. Use the **Sentinel misses its report deadline** scenario to show the investigation and recovery.

## Evidence and release status

| Claim | Evidence available |
| --- | --- |
| Local team rehearsal | Browser walkthrough with sample Gateway receipt, worker-cluster investigation and GitLab, ServiceNow or custom output |
| Existing Sentinel reference | The repository contains an older cluster-health Sentinel with a suspended schedule and log-only reporting default |
| Workplace BYO flow | Current product flow described by the owner. This bundle still needs an end-to-end Gateway and worker-cluster receipt. |
| Whisky GitLab board | Pending project opt-in and a correlated issue/read-back in the actual board |

The probe and carrier are Higgsfield concept art. The carrier represents the receiving agentic cluster. Use the workplace runbook to record receipts before presenting the flow as live.

## Present it in two minutes

1. Show the signal path and explain the two directions across the gateway boundary. The worker reports out, then the agent returns to the worker with scoped access.
2. Open Whisky and choose an investigation destination. Step through the finding, agent investigation and sample delivery. Switch to **Sentinel misses its report deadline** to show how the agent checks whether the monitor itself is working.
3. Close with the current Python alert cap and the planned Java classifier. Use the rehearsal labels while showing sample data.
