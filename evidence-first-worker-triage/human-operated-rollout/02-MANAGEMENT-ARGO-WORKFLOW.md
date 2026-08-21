# 2. Management Cluster — Event Bus, Argo and Workflow

Start only after the worker-side marker is confirmed in the approved Kafka
topic. This section proves the consumer/orchestration boundary without changing
the worker collector.

## 2.1 Discover the live management installation

```bash
kubectl --context "$MANAGEMENT_CONTEXT" get ns
kubectl --context "$MANAGEMENT_CONTEXT" get eventbus,eventsource,sensor -A
kubectl --context "$MANAGEMENT_CONTEXT" get workflowtemplate -A
kubectl --context "$MANAGEMENT_CONTEXT" get deploy -A | rg -i 'argo-events|workflow|kagent|aks-mcp'
```

Record the EventBus name, EventSource/Sensor/WorkflowTemplate names, installed
Argo Events and Argo Workflows versions, service accounts, existing Confluent
Secret/CA references, kagent endpoint, and GitLab credential reference. Reuse
the existing EventSource only if it already has the correct topic, group and
identity; otherwise create one additive, explicitly named consumer.

## 2.2 Confirm Kafka consumer permissions first

The EventSource principal must have `READ` on both the Kafka topic and the exact
consumer-group ID. `GROUP_AUTHORIZATION_FAILED` means the group binding is
missing even when the topic or an old group works.

Use the Confluent portal's **Add consumer group / Consumer onboarding** option,
bound to the service account/API key actually referenced by the EventSource.
Do not use producer onboarding and do not alter the old working consumer group.

## 2.3 Install/reconcile EventBus, EventSource, Sensor and Workflow in order

Adapt the management section of the pilot overlay against the discovered live
names, CRD schema and GitOps owner. Reconcile in this order:

1. Existing/approved EventBus health.
2. Kafka EventSource, with the approved topic, consumer group, Secret and CA
   references.
3. Sensor dependency/filter for the bounded evidence schema.
4. WorkflowTemplate: validation -> durable claim -> read-only diagnosis ->
   GitLab ticket.

Do a server-side dry run for each component, not a single blind bulk apply.

```bash
bash scripts/check-management-argo.sh --values /path/to/private/values.env --stage preflight
# Reconcile one approved component through GitOps, then:
bash scripts/check-management-argo.sh --values /path/to/private/values.env --stage eventsource
bash scripts/check-management-argo.sh --values /path/to/private/values.env --stage workflow
```

## 2.4 Prove Kafka -> EventSource -> Sensor -> Workflow

Use the same timestamp/marker proved on the worker side. Confirm in order:

1. The EventSource pod joins the intended consumer group without auth errors.
2. Consumer lag/offset advances past the marker in Confluent.
3. The Sensor receives its event and creates a workflow.
4. The Workflow validation step accepts the actual Kafka `body` contract.
5. The workflow receives the same bounded event fields expected from Vector.

```bash
bash scripts/check-management-argo.sh --values /path/to/private/values.env --stage all
kubectl --context "$MANAGEMENT_CONTEXT" -n "$MANAGEMENT_NAMESPACE" get workflows --sort-by=.metadata.creationTimestamp
argo -n "$MANAGEMENT_NAMESPACE" logs "$WORKFLOW_NAME" --all-containers
```

Do not accept a manually submitted Workflow as proof of the Kafka path. If the
workflow was not sensor-triggered, return to the EventSource/Sensor boundary.

## Management exit record

Capture EventBus/EventSource/Sensor conditions, EventSource log window,
consumer group offset evidence, workflow name, and a redacted incident payload
showing schema version, cluster, namespace, workload/pod, reason/signature,
severity and timestamp. Capture `container`/`service` only when the source
record genuinely contains them; event records should instead retain their
native object and event metadata. Then proceed to ticket/tool-quality work.
