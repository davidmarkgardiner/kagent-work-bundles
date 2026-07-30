# Split system and application triage paths

This is a replacement collection design for the single Alloy -> Vector path.
It is deliberately separate from `../config/`; do not apply both paths to the
same namespaces, or every signal will be duplicated.

## Two paths

| Path | Scope | Kafka topic | Consumer group | Ticket label |
|---|---|---|---|---|
| system | control-plane and platform namespaces | `{{SYSTEM_TRIAGE_TOPIC}}` | `{{SYSTEM_TRIAGE_GROUP}}` | `scope::system` |
| application | application and platform-service namespaces | `{{APPLICATION_TRIAGE_TOPIC}}` | `{{APPLICATION_TRIAGE_GROUP}}` | `scope::application` |

Each path has its own Alloy Deployment, Vector Deployment, Service, Kafka
topic, Kafka consumer group, EventSource and Sensors. A noisy application path
cannot fill the system receiver or its Kafka topic. The four workflow types
also carry `triage-scope` and `triage-signal` labels.

## Inputs

Replace every `{{PLACEHOLDER}}` in `config/`. Keep the namespace lists mutually
exclusive. `profiles/` is a concise, copyable inventory for review; the
deployable source of truth is `config/`.

The Vector deployments reuse the proven in-memory Kafka producer path. Do not
turn on Vector `buffer.type: disk` as a substitute for capacity testing: the
tested Vector image accepted that configuration but did not drain it to Kafka.
Alloy's current `emptyDir` preserves positions across a container restart but
not a Pod reschedule. Use a per-collector persistent volume only after proving
your storage class and restart behaviour; it is deliberately not guessed in
this portable bundle.

## Deployment sequence

1. Create the two Kafka topics and ACLs, then replace the five Kafka
   placeholders in `config/02-vector.yaml` and `config/03-argo-events.yaml`.
2. Confirm the shared prerequisites from `../config/` already exist:
   `alloy` ServiceAccount/RBAC, `confluent-credentials`, `argo-events-sa`,
   EventBus `default`, `red-agentic-triage` WorkflowTemplate and its
   `triage-workflow-concurrency` ConfigMap.
3. Set `{{CLUSTER_NAME}}` and `{{ENVIRONMENT}}` in `config/01-alloy.yaml`.
4. Render and apply just this replacement path:

   ```bash
   kubectl kustomize split-system-application/config
   kubectl apply -k split-system-application/config
   ```

5. Send one smoke marker through each topic/path and verify both a Kafka
   produced-message metric and one corresponding scoped Argo Workflow.
6. Stop the old `alloy-vector-triage` Deployment only after both split paths
   have independently passed that test. Do not run the old and split collectors
   against the same namespace for a normal smoke test: that duplicates signals.

## Included files

- `config/01-system-alloy.yaml` — the system Alloy ConfigMap and Deployment.
- `config/02-application-alloy.yaml` — the application Alloy ConfigMap and Deployment.
- `config/02-vector.yaml` — two isolated Vector receivers and Kafka sinks.
- `config/03-argo-events.yaml` — two EventSources and four scope/signal Sensors.
- `profiles/` — human-readable namespace, rollout and Kafka inventory only.

The existing shared WorkflowTemplate continues to create the GitLab ticket. It
receives `scope` in the incident JSON and the Workflow itself is labelled with
the scope. Add `scope::<value>` to the GitLab-label construction in that shared
template when you promote this replacement path; it is intentionally not
changed here because `../config/` remains the untouched single-path baseline.

## Controlled rollout

Use [`rollout-tiers/`](rollout-tiers/README.md) as the ordered policy source.
It keeps these two deployment pairs in place and changes only their signal
admission policy as capacity is proven: system-critical, then both lanes
critical, then both lanes priority.
