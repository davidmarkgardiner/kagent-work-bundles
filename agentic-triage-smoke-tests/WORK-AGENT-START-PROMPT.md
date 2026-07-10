# Work-Agent Start Prompt

You are validating an already-installed agentic triage system on a
non-production server or dev cluster. The alert path, webhook receiver, and
smart-triage fan-out are expected to already be configured in this
environment. Your job is to confirm the exact topology, then verify the
path end to end — not to build the pipeline from scratch.

## 0. Confirm Environment Topology Before Running Anything

Do not run any smoke until you have written down, for this specific
environment:

- Which cluster Grafana/Alertmanager alerts fire from (the "management
  cluster" or equivalent alert-origin cluster) and which cluster receives
  them.
- The full webhook delivery path. In some environments this is a direct
  `Grafana/Alertmanager -> smart-triage EventSource` hop (see
  `ALERTMANAGER-EVENT-ROUTING.md`). In others, the expected route is:

  ```text
  Grafana alert rule
  -> Alertmanager or Grafana webhook contact point
  -> Vector webhook receiver
  -> Vector normalize/router transform
  -> Kafka topic
  -> Kafka EventSource or consumer
  -> smart-triage Sensor
  -> Argo Workflow
  -> kagent triage system
  ```

  If Vector/Kafka is in the path, confirm all of these before creating any
  smoke pods or Grafana alerts:
  - the Vector endpoint that receives the Grafana/Alertmanager webhook;
  - the Vector transform that normalizes the payload;
  - the Kafka bootstrap, topic name, consumer group, and EventSource/Sensor
    that picks the message up, without printing credentials;
  - the exact join keys that survive each hop: `run_id`, `fingerprint`,
    `alertname`, `namespace`, `workload`, `source_type`, and `severity`;
  - one read-only evidence command for each hop: Vector received count/log,
    Kafka topic message, EventSource consumed event, Sensor-created Workflow;
  - what Vector does to the payload (pass-through vs. transform/re-shape);
  - that `run_id`/fingerprint and alert labels survive the Vector/Kafka hop
    unmodified, or document exactly what changes;
  - the downstream address or topic Vector forwards to, and that it matches the
    Kafka EventSource or smart-triage consumer actually used by this cluster.
- The real values for every placeholder in
  `requests/agentic-triage-smoke-request.yaml` (cluster, namespace, workload,
  Grafana contact point, alert route, Argo/Argo Events namespaces, model
  config). Do not assume the Proxmox POC values apply.
- The image source policy for smoke pods. Check whether this cluster can pull
  public images or must use a local registry/mirror. If local registry is
  required, replace example images such as `busybox:1.36` and
  `registry.k8s.io/pause:3.10` with approved local-registry equivalents before
  applying manifests. Record the final image names in the evidence.
- Whether the webhook, EventSource, Sensor, and WorkflowTemplate are already
  applied and Ready in this environment, or still need to be applied per
  `SMOKE-RUNBOOK.md` section 2.

Use the **Grafana MCP tools** available in your session to inspect and
configure Grafana alert rules and contact points/notification policies.
Do not hand-edit the Grafana UI or guess at API calls when MCP tooling can do
it. If Grafana MCP tools are not available in your session, stop and report
that as a blocker before proceeding.

Important: Loki log and Kubernetes event smokes do not require an additional
custom tool. They require normal LGTM configuration:

```text
pod logs -> Alloy or Promtail -> Loki -> Grafana LogQL alert
Kubernetes events -> Alloy loki.source.kubernetes_events -> Loki -> Grafana LogQL alert
Grafana alert -> Alertmanager/contact point -> Vector or direct webhook -> triage
```

Before declaring the log or event source unsupported, check whether the missing
piece is simply YAML/configuration:

- Alloy or Promtail is not scraping pod logs into Loki;
- Alloy `loki.source.kubernetes_events` is not configured;
- Loki labels differ from the example LogQL queries;
- Grafana has no LogQL alert rule for the smoke marker or event reason;
- the Grafana notification policy/contact point does not route
  `source_type=logs` or `source_type=events` to the triage webhook path;
- Vector/Kafka normalization drops `run_id`, `fingerprint`, `namespace`,
  `workload`, or `source_type`.

Metric alerts do not automatically include nearby logs/events. If the metric
smoke needs log/event context, verify that an enrichment step or agent-side
Loki query is present. Log and event smokes should be generated as first-class
Grafana Loki alerts.

State explicitly in your first status update: "environment topology
confirmed" plus:

- Vector/Kafka or direct-webhook answer;
- Kafka topic and EventSource/Sensor names if Vector/Kafka is used;
- Grafana MCP availability;
- image registry policy and chosen smoke images;
- whether any prerequisite is blocked.

Do not proceed to smoke execution until those are known.

## Steps

1. Read `work-agent-bundles/agentic-triage-smoke-tests/README.md`.
2. Read `work-agent-bundles/agentic-triage-smoke-tests/SMOKE-RUNBOOK.md`.
3. Read `work-agent-bundles/agentic-triage-smoke-tests/ALERTMANAGER-EVENT-ROUTING.md`
   and compare it against what you confirmed in step 0. Note any divergence
   (e.g. Vector hop not described there) in your evidence.
4. Verify or install the normal configuration needed for first-class Loki
   source alerts:
   - pod log ingestion into Loki for the smoke namespace;
   - Kubernetes event ingestion into Loki using Alloy
     `loki.source.kubernetes_events` or an equivalent approved event exporter;
   - Grafana LogQL alert rules for `log-errorburst` and
     `event-failedscheduling`;
   - notification routing for `source_type=logs` and `source_type=events`
     into the same Vector/direct webhook path as metrics.
   If any item is absent, document the exact missing config and either apply
   the approved YAML/config through the work process or mark that smoke red.
   Start from these tested bundle assets and adapt them to the installed
   versions rather than recreating the queries from memory:
   - `examples/monitoring/promtail-smoke-namespace-values.yaml`;
   - `examples/alloy/kubernetes-events-to-loki.yaml`;
   - `examples/grafana/source-type-alert-rules.yaml`;
   - `examples/k8s/crashloop-smoke-target.yaml`;
   - `examples/k8s/failed-scheduling-smoke-target.yaml`.
   Do not claim container-image enrichment unless a structured `image` field is
   visible in the firing webhook payload; image was not part of the live proof.
5. Fill `requests/agentic-triage-smoke-request.yaml` with the work-environment
   values confirmed in step 0. Do not write secrets into repo files.
6. Run `scripts/verify-bundle.sh`.
7. Run the runtime readiness gate in
   `work-agent-bundles/kagent-agentic-cluster-smoke-tests.md`.
8. Import or verify an equivalent Grafana dashboard for general stack health
   using `examples/grafana/agentic-triage-stack-health-dashboard.json`.
   Use Grafana MCP if available. Confirm panels or replacement queries cover
   kagent agent readiness, agentgateway request health, workflow health,
   EventSource/Sensor pods, Vector/Kafka health when used, smoke freshness, and
   source coverage.
9. Execute the smoke matrix for metrics, logs, events, traces or trace fallback,
   dedup, and one negative health case.
10. Capture evidence in `evidence/EVIDENCE-TEMPLATE.md`, including the
   confirmed topology from step 0 and, if Vector is in the path, one sample
   showing the alert payload before and after Vector.

Stop and report red if direct agentgateway/model or single A2A completion
fails. Do not keep testing Grafana alert routing until the core request path is
healthy.

Required final answer:

- confirmed topology: alert-origin cluster, receiving cluster, and whether
  Vector or a direct webhook sits in front of the smart-triage EventSource;
- verdict: `red`, `amber`, or `green`;
- smoke matrix result table;
- links or names for workflows, Grafana dashboards, and eval reports;
- confirmation that stack-health dashboard coverage exists for kagent,
  agentgateway, workflows, EventSource/Sensor, Vector/Kafka if used, smoke
  freshness, and source coverage;
- exact failures and next owner;
- confirmation that no production workload was mutated.
