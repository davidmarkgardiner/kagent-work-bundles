# Two-Cluster Grafana Chaos Verification

## Goal

Prove the real work flow end to end across both clusters:

```text
management cluster:
Grafana + Prometheus + test workload / chaos target
  -> Grafana alert rule fires
  -> approved contact point posts to Vector webhook

event / automation cluster:
Vector webhook receiver
  -> normalize / filter / dedupe / route
  -> Kafka actionable topic
  -> Argo EventSource / Sensor
  -> Argo Workflow
  -> triage agent
  -> optional specialist agent handoff
  -> GitLab ticket or ServiceNow escalation
```

The agent must have kubeconfig access to both clusters and must explicitly
record which context is used for each action.

## Required Access

The work agent needs:

- `{{MGMT_KUBE_CONTEXT}}`: cluster running Grafana, Prometheus, and the approved
  chaos/test namespace.
- `{{EVENTS_KUBE_CONTEXT}}`: cluster running Vector, Kafka access, Argo Events,
  Argo Workflows, and the agent workflow path.
- Grafana write access through one of:
  - Grafana MCP with alert/contact-point write tools;
  - Grafana CLI/API using approved admin credentials;
  - approved Grafana UI path if automation is blocked.
- Existing Grafana contact point that posts to the Vector webhook receiver.
- GitLab or ServiceNow target for final evidence.

Do not print passwords, tokens, private endpoints, tenant IDs, subscription IDs,
or kubeconfig contents. Record names, UIDs, contexts, namespaces, and redacted
URLs only.

## Run Order

1. Confirm both kube contexts:

   ```bash
   kubectl --context {{MGMT_KUBE_CONTEXT}} cluster-info
   kubectl --context {{EVENTS_KUBE_CONTEXT}} cluster-info
   ```

2. On the management cluster, confirm Prometheus is scraping the target
   namespace and Grafana can query the datasource.

3. Programmatically create or update the chaos alert rules in Grafana using:

   ```text
   examples/grafana-chaos-alerts/chaos-alert-rules.yaml
   ```

   Preferred path: Grafana MCP. The agent should discover the available
   Grafana MCP tools, then create or update the `Kagent Chaos Gameday` folder,
   alert rules, and notification policy. Record the MCP tool names used.

   Fallback path: Grafana HTTP API/CLI using the approved admin credential:

   ```bash
   cd examples/grafana-chaos-alerts
   export GRAFANA_URL="{{GRAFANA_URL}}"
   export GRAFANA_USER="{{GRAFANA_USER}}"
   export GRAFANA_PASSWORD="{{GRAFANA_PASSWORD}}"
   export CHAOS_TARGET_NAMESPACE="{{CHAOS_TARGET_NAMESPACE}}"
   export GRAFANA_CREATE_PAUSED="true"
   bash create-chaos-alerts-api.sh
   ```

   The rule must be created paused first. Only unpause the one rule being
   tested after the contact point, notification policy, chaos rollback, and
   events-cluster readiness are confirmed.

4. Point the alert rules at the approved contact point that forwards to the
   Vector webhook receiver. Keep the rules paused until the contact point,
   notification policy, and rollback are confirmed.

5. On the events/automation cluster, confirm:

   ```bash
   kubectl --context {{EVENTS_KUBE_CONTEXT}} -n {{ARGO_EVENTS_NAMESPACE}} get deploy
   kubectl --context {{EVENTS_KUBE_CONTEXT}} -n {{ARGO_EVENTS_NAMESPACE}} get eventsource,sensor
   kubectl --context {{EVENTS_KUBE_CONTEXT}} -n {{ARGO_WORKFLOWS_NAMESPACE}} get workflowtemplates
   ```

6. Unpause the selected alert rule, then inject one approved low-risk chaos
   scenario on the management cluster. Prefer a dedicated namespace such as
   `{{CHAOS_TARGET_NAMESPACE}}`.

7. Verify the chain in order:

   ```text
   Grafana alert state = firing
   contact point delivery = successful
   Vector received webhook = logged or metric observed
   Kafka actionable topic = one normalized record
   Argo EventSource/Sensor = event accepted
   Argo Workflow = created
   triage agent = selected
   specialist handoff = selected if needed
   GitLab/ServiceNow = ticket created or updated
   ```

8. Roll back the chaos condition, confirm alert recovery, and confirm the
   recovery/resolved notification does not create a new actionable agent task.

9. Clean up before moving to the next scenario:

   ```text
   Grafana alert rule paused or deleted
   Grafana alert state returned to normal/resolved
   chaos resource removed or reverted
   test workload restored
   Argo workflows from the run completed or cleaned up
   no duplicate workflow created from the resolved alert
   GitLab/ServiceNow ticket updated with final state
   ```

   Do not start the next scenario until this cleanup gate passes.

## Scenario Rollout

Run one scenario correctly before expanding. The recommended order is:

1. Pod restart spike: simplest AKS/SRE route and lowest blast radius.
2. Ingress 5xx/latency: proves network specialist handoff.
3. Policy/security violation: proves security-hardening route.
4. Certificate expiry or TLS failure: proves platform/cert-manager route.

Use `scenarios/SCENARIO-PACK.md` for the full scenario table and expected
ticket evidence. Each scenario should follow the same lifecycle:

```text
create/update paused alert rule
  -> confirm contact point
  -> unpause only that rule
  -> inject approved chaos
  -> prove alert fired
  -> prove Vector/Kafka/Argo/agent/ticket path
  -> roll back chaos
  -> confirm alert resolved
  -> pause/delete test alert rule
  -> clean up workflows and test resources
```

## Cleanup Requirements

The run is not complete until the agent proves nothing is left running.

Grafana cleanup:

- pause or delete the temporary chaos alert rule;
- confirm the alert is no longer firing;
- confirm notification policy changes are either retained intentionally or
  reverted;
- record alert rule UID and final state.

Kubernetes cleanup on the management cluster:

- remove or revert the chaos object/change;
- confirm the test workload is healthy;
- confirm Prometheus metrics return to normal.

Kubernetes cleanup on the events/automation cluster:

- confirm the Argo workflow reached a terminal state;
- delete disposable test workflows if the retention policy requires it;
- confirm no duplicate workflow was created by the resolved alert;
- confirm Vector and Argo controllers remain healthy.

Ticket cleanup:

- update the GitLab/ServiceNow ticket with final state:
  `triaged`, `remediated`, `rolled_back`, `escalated`, or `blocked`;
- include rollback evidence and links to the workflow/dashboards.

## Evidence To Capture

Return a short evidence pack:

```text
MGMT_KUBE_CONTEXT:
EVENTS_KUBE_CONTEXT:
GRAFANA_FOLDER_UID:
GRAFANA_ALERT_RULE_UID:
GRAFANA_CONTACT_POINT:
CHAOS_TARGET_NAMESPACE:
CHAOS_SCENARIO:
ALERT_FIRED_AT:
VECTOR_RECEIVED_AT:
KAFKA_TOPIC:
KAFKA_OFFSET_OR_RECORD_ID:
ARGO_EVENTSOURCE:
ARGO_SENSOR:
ARGO_WORKFLOW_NAME:
TARGET_AGENT:
SPECIALIST_HANDOFF:
GITLAB_ISSUE_OR_SERVICENOW_ID:
ROLLBACK_CONFIRMED:
ALERT_RESOLVED:
GRAFANA_RULE_PAUSED_OR_DELETED:
CHAOS_RESOURCE_CLEANED:
WORKFLOW_TERMINAL_OR_CLEANED:
NO_DUPLICATE_WORKFLOW:
OUTPUT_SANITIZED: yes
```

## Home-Lab Evidence Already Captured

The public/home-lab work already proved the delivery mechanics that this
two-cluster test builds on:

- Direct HTTP receiver pattern:

  ```text
  Raw Alertmanager webhook
    -> vector-alert-webhook-normalizer /alerts
    -> alertmanager-events-triage
    -> vector-alertmanager-triage-kafka EventSource
    -> vector-alertmanager-triage Sensor
    -> alert-triage-vector-rpwvn
  ```

  Evidence recorded in:
  `payload/observability-vector/homelab/README.md`

- Kafka-first pattern:

  ```text
  Alertmanager-style payload
    -> alertmanager-events
    -> vector-alertmanager-normalizer
    -> alertmanager-events-triage
    -> vector-alertmanager-triage-kafka EventSource
    -> vector-alertmanager-triage Sensor
    -> alert-triage-vector-jnpz9
  ```

  Evidence recorded in:
  `payload/observability-vector/homelab/README.md`

- Vector normalization, filtering, and dedupe cases were tested with the Vector
  container using:

  ```text
  payload/observability-vector/tests/run-vector-example-tests.sh
  payload/observability-vector/tests/vector-example-test.yaml
  ```

The home lab did not prove the work-specific two-cluster Grafana contact point,
Prometheus scrape path, or GitLab/ServiceNow ticket creation. The work agent
must prove those live using this runbook and
`prompts/07-chaos-gameday-end-to-end.md`.
