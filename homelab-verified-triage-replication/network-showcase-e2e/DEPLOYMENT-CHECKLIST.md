# Work deployment checklist — network showcase E2E

Use this checklist to lift `network-showcase-e2e/` into the work repository.
It is ordered by dependency: do not start the smoke corpus until the agents,
Kafka consumer, and workflow route are proven. Keep all environment-specific
values in the work repository or its secret-management system; do not copy
credentials into this public bundle.

## Demo goal

For every Alloy-watched namespace, the demo produces one ticket for each
signal type (one log and one Kubernetes Event). The primary triage agent uses
A2A to call the evaluation agent for every ticket and, when its own diagnosis
indicates a network, DNS, connectivity, dropped-traffic, or network-policy
issue, it calls the network-flow agent too. The ticket carries the independent
evaluation verdict and score.

## Phase 0 — prerequisites (verify, do not assume)

- [ ] `kagent` and its tool bridge are Ready: either `kagent-tool-server`, or
  the work `aks-mcp` `RemoteMCPServer` used by the primary agent.
- [ ] `argo-events/gitlab-credentials` exists and contains `url`, `token`, and
  `project-id`.
- [ ] `confluent-credentials` exists and contains `bootstrap`, `key`, and
  `secret`; record the actual Kafka topic and the consumer-group name to use.
- [ ] The Argo `EventBus` and `argo-events-sa` exist in the expected namespace.
- [ ] Copy the complete `network-showcase-e2e/` directory into the work repo.
- [ ] Confirm the target Kubernetes context and namespace ownership before any
  apply. The homelab `red` context is not evidence of work-cluster readiness.

## Phase 1 — backend agents (A2A fan-out)

- [ ] Apply `triage-evaluation-agent`.
- [ ] Apply `aks-network-flow-triage`:
  - [ ] If a read-only `hubble-mcp` `RemoteMCPServer` is onboarded, keep its
    binding for cluster-wide Cilium/Hubble flow, DNS, drop, and policy evidence.
  - [ ] Otherwise deploy the Kubernetes-only variant by removing the
    `hubble-mcp` binding. The agent must explicitly mark flow findings
    **UNVERIFIED** rather than failing reconciliation.
- [ ] Set the work primary agent to `aks-mcp-readonly-triage-agent` from
  `work-evaluation-overlay`.
- [ ] Mount both sub-agents on that primary as native `type: Agent` tools:
  - [ ] `triage-evaluation-agent`
  - [ ] `aks-network-flow-triage`
- [ ] Add the conditional network-routing instruction from
  `agents/10-primary-triage-agent.yaml` to the primary's `systemMessage`:
  call the network agent for network/DNS/connectivity evidence; skip it when
  it would not add relevant evidence.
- [ ] Confirm all three Agents report `Accepted=True` and `Ready=True`.

## Phase 2 — workflow routing to the primary agent

- [ ] Deploy the pipeline from `pipeline/`, or the corresponding work
  evaluation overlay: Alloy → Vector → Kafka → Argo.
- [ ] Render the Kafka `EventSource` before applying it. `deploy.sh` does **not**
  replace these fields:
  - [ ] `url` ← `confluent-credentials.bootstrap`
  - [ ] `topic` ← the actual topic that Vector publishes to
  - [ ] `consumerGroup.groupName` ← a stable, environment-specific group name
- [ ] Confirm the EventSource pod is `Running` with **0 restarts**. An
  unrendered URL can crash-loop with `missing port in address`.
- [ ] Set `05-triage-evaluation-settings` `triage-agent-url` to
  `aks-mcp-readonly-triage-agent`.
- [ ] Increase the workflow `max-time` above 240 seconds. The triage →
  network A2A → evaluation A2A chain is slow on network-shaped incidents.
- [ ] Confirm the Sensor consumes the selected topic and creates the
  `red-agentic-triage`-equivalent workflow.
- [ ] Keep the consumer bounded to the intended demo scope. A shared
  `k8s-events` topic is a cluster-wide warning/error firehose; pause the
  EventSource deployment when the demo is not running if required by the
  operating model.

## Phase 3 — smoke test each namespace

- [ ] Set Alloy's namespace allow-list to the intended target namespaces.
- [ ] Regenerate the corpus for that exact list:

  ```bash
  smoke/all-namespaces/generate.sh <namespace-1> <namespace-2> ...
  ```

- [ ] Confirm Alloy tails newly created pods. If the first signals do not
  create workflows, restart the Alloy pod to re-discover targets, then retry
  with a unique token or pod name: Vector deduplicates identical signals.
- [ ] Apply the smoke corpus:

  ```bash
  kubectl --context <context> apply -k smoke/all-namespaces
  ```

- [ ] Expect two tickets per namespace: one log signal and one Event signal.

## Phase 4 — prove the demo goals

- [ ] **Per-namespace coverage:** one ticket per signal type per namespace.
- [ ] **A2A in use:** controller history or agent logs show the primary calling
  its sub-agents.
- [ ] **Evaluation score:** each ticket contains
  `| Evaluation | PASS (score X/10) |` and the score legend.
- [ ] **Conditional network hop:** `smoke/10-network-smoke.yaml` drives a call
  to `aks-network-flow-triage`; non-network signals do not require that hop.
  This is the primary agent's evidence-led reasoning, not a hard-coded Sensor
  branch.
- [ ] Run the read-only verification:

  ```bash
  scripts/verify-smoke.sh --context <context> --path v2
  ```

- [ ] Tear down fixtures after review:

  ```bash
  kubectl --context <context> delete -k smoke/all-namespaces
  kubectl --context <context> delete -k smoke
  ```

## Evidence to retain

- Agent conditions for all three Agents.
- EventSource pod status and restart count after Kafka values are rendered.
- Sensor/workflow evidence for every expected namespace and signal type.
- Primary-agent A2A controller history or logs for evaluation and conditional
  network calls.
- Ticket URLs or redacted ticket excerpts showing evaluation score and legend.
