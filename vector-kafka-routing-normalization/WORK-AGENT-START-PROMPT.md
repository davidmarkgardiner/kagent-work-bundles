# Work-Agent Start Prompt

```text
You are the work-side implementation agent for Vector Kafka routing
normalization.

You have been given a self-contained folder named:

vector-kafka-routing-normalization

You only need this folder. It contains the start prompt, checklists, scenario
pack, Grafana chaos examples, dashboard example, and Vector reference payload
under:

payload/observability-vector/

Your job is not to explain the theory. Your job is to verify the live work
environment, confirm the existing prerequisites, adapt the public-safe
manifests, and return evidence.

Important baseline from the work environment:

Yesterday the team proved an end-to-end flow:

```text
Alertmanager / Grafana alert
  -> Kenawa webhook
  -> Vector
  -> webhook-to-Kafka proxy
  -> Kafka
  -> Argo EventSource / Sensor
  -> Argo Workflow
```

Treat that as the working baseline. Do not break it, bypass it, delete it, or
replace it as your first action. Your job is to iterate over that proven flow:
document it, make Vector's filtering/dedupe/routing stricter, prove only
actionable alerts reach the Kafka topic consumed by Argo, and only then propose
any cleaner path or proxy removal.

The main design goal is efficiency and signal quality:

- Vector is the cleanup and routing boundary.
- The actionable Kafka topic must contain only alerts that an agent should
  inspect.
- Resolved alerts, non-actionable severities, missing-owner noise, duplicate
  alert repeats, heartbeat/test traffic, and known-ignored Alertmanager noise
  must not create agent work.
- Raw events may be retained in a raw/audit topic where required, but the
  normalized/actionable topic must be clean enough for Argo to trust.
- Argo should consume normalized actionable records only. It should not contain
  the main filtering, dedupe, or noise-suppression logic.

First, from inside this folder, run:

bash scripts/verify-bundle.sh

If the bundle verifier fails, stop and report the exact missing or invalid file.

Important work-environment assumption: Vector is already deployed, Confluent
connectivity is already configured, and the Manager/Grafana contact point is
already present. Do not recreate those blindly. First discover the existing
resources and record where they are.

Also assume the Kenawa webhook and webhook-to-Kafka proxy are part of the
currently working flow until your evidence proves otherwise. Preserve them while
testing improvements in parallel.

Before any live Kafka, Confluent, Vector, Argo Events, Grafana, Alloy, or
Kubernetes change, run:

prompts/01-preflight-env-tools.md

Do not proceed unless required variables, tools, namespaces, image names,
connection-secret locations, and Grafana MCP/contact-point access are confirmed,
or mark the run BLOCKED with the exact missing item names. Do not print secret
values.

Then complete the work in this order:

1. Read FRONT-SHEET.md, README.md, CHECKLIST.md, and
   requests/vector-routing-normalization-request.yaml.
2. Read PREREQS-CHECKLIST.md, payload/REFERENCE.md, and
   payload/observability-vector/handoff/FEEDBACK.md.
3. Run prompts/01-preflight-env-tools.md.
4. Confirm the existing Vector deployment, image, namespace, config source,
   service account, Confluent secret references, and exposed health/API port.
5. Confirm the Kenawa webhook, webhook-to-Kafka proxy, Kafka topic, Argo
   EventSource, Argo Sensor, and Argo Workflow that participated in yesterday's
   working path.
6. Confirm the Manager/Grafana contact point and notification route using
   Grafana MCP or approved Grafana tooling.
7. Run prompts/02-deploy-vector-normalizer.md.
8. Create a new Vector instance or config off the existing Vector pattern only
   after the discovery gate passes.
9. Run prompts/03-verify-routing-and-dedupe.md.
10. Run prompts/04-run-grafana-mcp-end-to-end.md.
11. Use Grafana MCP to fire or trigger a safe test alert through the existing
   contact point, then prove Vector publishes back to Confluent, Argo consumes
   the normalized event, the production triage workflow runs, the kit/kagent
   analysis executes, and a GitLab ticket/issue is created.
12. Prove app, platform, security, and fallback route decisions where test data
   is approved.
13. Prove duplicate suppression before the actionable Kafka topic and before
   Argo workflow creation.
14. Prove filtering before the actionable Kafka topic:
   - resolved Alertmanager alerts are dropped
   - resolved Grafana alerts are dropped
   - configured ignored severities are dropped or quarantined
   - configured ignored namespaces/services are dropped or quarantined
   - repeat notifications for the same firing alert produce one actionable
     record inside the dedupe window
   - malformed or incomplete payloads do not trigger Argo
15. Confirm whether dropped/noisy records are discarded, counted in metrics, or
   written to a quarantine topic. If a quarantine topic is used, prove Argo does
   not consume it.
16. Run prompts/05-production-readiness-gap-check.md.
17. Run prompts/06-assess-existing-webhook-proxy-cleanup.md if the work
   environment has an existing webhook/proxy/Confluent REST chain or if the
   team wants a component-reduction recommendation.
18. After the most efficient baseline flow is delivering actionable events and
   the filtering/dedupe checks have passed, run
   prompts/07-chaos-gameday-end-to-end.md for at least one approved scenario if
   the team has approved a safe test window. This must exercise the whole flow:
   controlled fault -> Alertmanager/Grafana alert -> Kenawa webhook -> Vector
   cleanup -> Kafka -> Argo -> agent triage/remediation path -> GitLab ticket
   updated with evidence.
19. Return the evidence template filled in.

Required evidence markers:

- BUNDLE_VERIFY: passed
- ENV_PREFLIGHT: passed_or_blocked
- EXISTING_VECTOR: discovered
- WORK_BASELINE_CHAIN: documented
- KENAWA_WEBHOOK: verified
- WEBHOOK_TO_KAFKA_PROXY: verified
- VECTOR_IMAGE: captured
- VECTOR_NAMESPACE: captured
- CONFLUENT_CONNECTION_SECRET: located
- GRAFANA_MCP: available_or_blocked
- MANAGER_CONTACT_POINT: verified
- TOPICS: verified_or_created
- VECTOR_CONFIG: validated
- K8S_DRY_RUN: passed
- VECTOR_ROLLOUT: healthy
- RAW_KAFKA_RECORD: produced
- NORMALIZED_KAFKA_RECORD: consumed
- GRAFANA_TEST_ALERT: firing
- MANAGER_CONTACT_POINT_DELIVERY: verified
- ARGO_SENSOR_TRIGGER: verified
- TRIAGE_WORKFLOW: succeeded_or_expected_terminal_state
- KIT_AGENT_ANALYSIS: captured
- GITLAB_TICKET: created
- GITLAB_TICKET_TRIAGE_OR_REMEDIATION: verified
- ROUTE_APP: verified
- ROUTE_PLATFORM: verified
- ROUTE_SECURITY: verified
- ROUTE_FALLBACK: verified
- ACTIONABLE_TOPIC_CLEAN: verified
- DEDUPE: verified
- RESOLVED_FILTER: verified
- NOISE_FILTER: verified
- MALFORMED_PAYLOAD_FILTER: verified
- QUARANTINE_DECISION: discard_metric_or_topic
- CURRENT_CHAIN: documented
- CLEAN_CHAIN: proposed_or_verified
- AUTH_OPTIONS: verified
- OAUTH_DECISION: supported_blocked_or_not_available
- API_KEY_FALLBACK: documented
- PROXY_REMOVAL_DECISION: remove_keep_or_blocked
- ROLLBACK_PLAN: captured
- FULL_ENVELOPE_WORKFLOW: planned_or_implemented
- AUTOMATION_GATE: default_deny
- METRICS_PLAN: captured
- CLEANUP: completed_or_not_requested
- OUTPUT_SANITIZED: yes

Return this format:

STATUS: PASS | PARTIAL | BLOCKED
COMMANDS_RUN:
ENV_PREFLIGHT:
EXISTING_VECTOR:
GRAFANA_MCP:
MANAGER_CONTACT_POINT:
TOPICS:
VECTOR:
ARGO_EVENTS:
ROUTING:
DEDUPE:
FILTERING:
ACTIONABLE_TOPIC:
NOISE_SUPPRESSION:
QUARANTINE:
GRAFANA_E2E:
CHAOS_E2E:
GITLAB_TICKET:
WEBHOOK_PROXY_ASSESSMENT:
BASELINE_PRESERVATION:
WORKFLOW_CONTRACT:
AUTOMATION_GATE:
METRICS:
CLEANUP:
FILES_OR_EVIDENCE:
GAPS:
NEXT_ACTION:

Do not print or commit secret values. Do not expose private endpoints. Use
environment variable names and redacted hostnames in reusable output.
```
