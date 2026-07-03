#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BUNDLE_ROOT}"

echo "== Vector Kafka routing normalization work-agent bundle verifier =="
echo "bundle: ${BUNDLE_ROOT}"
echo "mode: local/static; no Kafka, Confluent, cluster, or Grafana calls"

required=(
  "FRONT-SHEET.md"
  "PREREQS-CHECKLIST.md"
  "README.md"
  "WORK-AGENT-START-PROMPT.md"
  "CHECKLIST.md"
  "GITLAB-TICKET.md"
  "requests/vector-routing-normalization-request.yaml"
  "prompts/01-preflight-env-tools.md"
  "prompts/02-deploy-vector-normalizer.md"
  "prompts/03-verify-routing-and-dedupe.md"
  "prompts/04-run-grafana-mcp-end-to-end.md"
  "prompts/05-production-readiness-gap-check.md"
  "prompts/06-assess-existing-webhook-proxy-cleanup.md"
  "prompts/07-chaos-gameday-end-to-end.md"
  "examples/grafana-chaos-alerts/README.md"
  "examples/grafana-chaos-alerts/chaos-alert-rules.yaml"
  "examples/grafana-chaos-alerts/create-chaos-alerts-api.sh"
  "examples/grafana-dashboards/lgtm-agentic-resolution-showcase.json"
  "examples/daily-gameday/cronworkflow.yaml"
  "SHOWCASE-RUNBOOK.md"
  "scenarios/SCENARIO-PACK.md"
  "TICKET-QUALITY-CONTRACT.md"
  "FAILURE-MODE-TESTS.md"
  "PROMOTION-GATE.md"
  "TWO-CLUSTER-CHAOS-README.md"
  "payload/REFERENCE.md"
  "payload/observability-vector/README.md"
  "payload/observability-vector/manifests/01-vector-alertmanager-normalizer.yaml"
  "payload/observability-vector/manifests/02-argo-alertmanager-triage-topic.yaml"
  "payload/observability-vector/manifests/03-argo-routing-verification.yaml"
  "payload/observability-vector/tests/run-vector-example-tests.sh"
  "payload/observability-vector/tests/vector-example-test.yaml"
  "payload/observability-vector/handoff/FEEDBACK.md"
  "payload/observability-vector/homelab/README.md"
  "payload/observability-vector/homelab/vector-http-receiver-to-kafka.yaml"
  "payload/observability-vector/homelab/vector-kafka-raw-to-normalized.yaml"
  "evidence/EVIDENCE-TEMPLATE.md"
)

for rel in "${required[@]}"; do
  if [[ ! -f "${rel}" ]]; then
    echo "MISSING ${rel}" >&2
    exit 1
  fi
  echo "FOUND ${rel}"
done

for marker in \
  "BUNDLE_VERIFY: passed" \
  "ENV_PREFLIGHT: passed_or_blocked" \
  "EXISTING_VECTOR: discovered" \
  "WORK_BASELINE_CHAIN: documented" \
  "KENAWA_WEBHOOK: verified" \
  "WEBHOOK_TO_KAFKA_PROXY: verified" \
  "VECTOR_IMAGE: captured" \
  "VECTOR_NAMESPACE: captured" \
  "CONFLUENT_CONNECTION_SECRET: located" \
  "GRAFANA_MCP: available_or_blocked" \
  "MANAGER_CONTACT_POINT: verified" \
  "VECTOR_CONFIG: validated" \
  "GRAFANA_TEST_ALERT: firing" \
  "MANAGER_CONTACT_POINT_DELIVERY: verified" \
  "ARGO_SENSOR_TRIGGER: verified" \
  "TRIAGE_WORKFLOW: succeeded_or_expected_terminal_state" \
  "KIT_AGENT_ANALYSIS: captured" \
  "GITLAB_TICKET: created" \
  "ROUTE_APP: verified" \
  "ROUTE_PLATFORM: verified" \
  "ROUTE_SECURITY: verified" \
  "ROUTE_FALLBACK: verified" \
  "DEDUPE: verified" \
  "RESOLVED_FILTER: verified" \
  "CURRENT_CHAIN: documented" \
  "CLEAN_CHAIN: proposed_or_verified" \
  "AUTH_OPTIONS: verified" \
  "OAUTH_DECISION: supported_blocked_or_not_available" \
  "API_KEY_FALLBACK: documented" \
  "PROXY_REMOVAL_DECISION: remove_keep_or_blocked" \
  "ROLLBACK_PLAN: captured" \
  "CHAOS_PREFLIGHT: passed" \
  "GRAFANA_MCP_ALERT_WRITE: used_or_blocked" \
  "GRAFANA_CHAOS_ALERT_RULES: created_or_updated" \
  "CHAOS_SCENARIO: injected" \
  "GRAFANA_ALERT_FIRED: verified" \
  "VECTOR_ROUTE_AGENT: verified" \
  "SPECIALIST_AGENT_SELECTED: verified" \
  "TICKET_CREATED_OR_UPDATED: verified" \
  "CHAOS_ROLLBACK: verified" \
  "GRAFANA_DASHBOARD: updated" \
  "DAILY_GAMEDAY_PROPOSAL: captured" \
  "AUTOMATION_GATE: default_deny" \
  "OUTPUT_SANITIZED: yes"; do
  grep -q "${marker}" "WORK-AGENT-START-PROMPT.md" "GITLAB-TICKET.md" "evidence/EVIDENCE-TEMPLATE.md" "prompts/07-chaos-gameday-end-to-end.md"
  echo "MARKER_OK ${marker}"
done

grep -q "automation_allowed" "payload/REFERENCE.md"
grep -q "default-deny" "payload/REFERENCE.md" "FRONT-SHEET.md" "CHECKLIST.md"
grep -q "{{MGMT_KUBE_CONTEXT}}" "PREREQS-CHECKLIST.md"
grep -q "{{ALERTMANAGER_RAW_TOPIC}}" "PREREQS-CHECKLIST.md"
grep -q "{{ALERTMANAGER_TRIAGE_TOPIC}}" "PREREQS-CHECKLIST.md"
grep -q "Vector is already running" "README.md" "prompts/01-preflight-env-tools.md"
grep -q "Grafana MCP" "WORK-AGENT-START-PROMPT.md" "prompts/01-preflight-env-tools.md"
grep -q "GitLab ticket" "WORK-AGENT-START-PROMPT.md" "prompts/04-run-grafana-mcp-end-to-end.md"
grep -q "production triage workflow" "WORK-AGENT-START-PROMPT.md" "prompts/04-run-grafana-mcp-end-to-end.md"
grep -q "Manager/Grafana contact point" "WORK-AGENT-START-PROMPT.md" "prompts/01-preflight-env-tools.md"
grep -q "webhook-to-Kafka proxy" "README.md" "FRONT-SHEET.md" "prompts/06-assess-existing-webhook-proxy-cleanup.md"
grep -q "SASL_PLAIN" "README.md" "prompts/06-assess-existing-webhook-proxy-cleanup.md"
grep -q "OAuth/OIDC" "README.md" "prompts/06-assess-existing-webhook-proxy-cleanup.md"
grep -q "HOME_LAB_REPLICATION" "prompts/06-assess-existing-webhook-proxy-cleanup.md" "evidence/EVIDENCE-TEMPLATE.md"
grep -q "vector-http-receiver-to-kafka.yaml" "README.md" "prompts/06-assess-existing-webhook-proxy-cleanup.md"
grep -q "vector-kafka-raw-to-normalized.yaml" "README.md" "prompts/06-assess-existing-webhook-proxy-cleanup.md"
grep -q "controlled chaos" "README.md" "prompts/07-chaos-gameday-end-to-end.md"
grep -q "chaos-alert-rules.yaml" "README.md" "prompts/07-chaos-gameday-end-to-end.md" "examples/grafana-chaos-alerts/README.md"
grep -q "create-chaos-alerts-api.sh" "README.md" "prompts/07-chaos-gameday-end-to-end.md" "examples/grafana-chaos-alerts/README.md"
grep -q "Grafana MCP" "prompts/07-chaos-gameday-end-to-end.md" "examples/grafana-chaos-alerts/README.md"
grep -q "daily low-risk verification job" "prompts/07-chaos-gameday-end-to-end.md"
grep -q "networking-triage-agent" "prompts/07-chaos-gameday-end-to-end.md"
grep -q "security-hardening-agent" "examples/grafana-chaos-alerts/chaos-alert-rules.yaml"
grep -q "platform-ops-agent" "examples/grafana-chaos-alerts/chaos-alert-rules.yaml"
grep -q "aks-sre-triage-agent" "examples/grafana-chaos-alerts/chaos-alert-rules.yaml"
grep -q "Grafana dashboards" "README.md" "prompts/07-chaos-gameday-end-to-end.md"
grep -q "LGTM To Agentic Resolution Showcase" "examples/grafana-dashboards/lgtm-agentic-resolution-showcase.json"
grep -q "suspend: true" "examples/daily-gameday/cronworkflow.yaml"
grep -q "Ticket Quality Contract" "TICKET-QUALITY-CONTRACT.md"
grep -q "Failure-Mode Tests" "FAILURE-MODE-TESTS.md"
grep -q "Promotion Gate" "PROMOTION-GATE.md"
grep -q "Known-Good Scenario Pack" "scenarios/SCENARIO-PACK.md"
grep -q "LGTM To Agentic Resolution Showcase Runbook" "SHOWCASE-RUNBOOK.md"
grep -q "VECTOR_SECRET_REFS_NAMES_ONLY" "prompts/01-preflight-env-tools.md"
grep -q "suppress_duplicates" "payload/observability-vector/manifests/01-vector-alertmanager-normalizer.yaml"
grep -q "accepted_events" "payload/observability-vector/manifests/01-vector-alertmanager-normalizer.yaml"
grep -q "readinessProbe" "payload/observability-vector/manifests/01-vector-alertmanager-normalizer.yaml"
grep -q "livenessProbe" "payload/observability-vector/manifests/01-vector-alertmanager-normalizer.yaml"
echo "PROMPT_CONTRACT_OK: yes"

public_safety_hits="$(
  grep -RInE \
    '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|pkc-[A-Za-z0-9-]+|lkc-[A-Za-z0-9-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' \
    --exclude='verify-bundle.sh' . \
    | grep -Ev 'sasl\.password: "\$\{CONFLUENT_SA_SECRET\}"|secret: "\{\{CONFLUENT_KAFKA_API_SECRET\}\}"' \
    || true
)"

if [[ -n "${public_safety_hits}" ]]; then
  echo "${public_safety_hits}"
  echo "PUBLIC_SAFETY_HITS: review output above" >&2
  exit 1
fi
echo "PUBLIC_SAFE_SCAN_OK: yes"

echo "VECTOR_KAFKA_ROUTING_NORMALIZATION_BUNDLE_VERIFY: passed"
