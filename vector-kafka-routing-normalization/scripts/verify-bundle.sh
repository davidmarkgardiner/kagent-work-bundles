#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${BUNDLE_ROOT}/../.." && pwd)"
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
  "payload/REFERENCE.md"
  "evidence/EVIDENCE-TEMPLATE.md"
)

for rel in "${required[@]}"; do
  if [[ ! -f "${rel}" ]]; then
    echo "MISSING ${rel}" >&2
    exit 1
  fi
  echo "FOUND ${rel}"
done

repo_required=(
  "observability/vector/README.md"
  "observability/vector/manifests/01-vector-alertmanager-normalizer.yaml"
  "observability/vector/manifests/02-argo-alertmanager-triage-topic.yaml"
  "observability/vector/manifests/03-argo-routing-verification.yaml"
  "observability/vector/tests/run-vector-example-tests.sh"
  "observability/vector/tests/vector-example-test.yaml"
  "observability/vector/handoff/FEEDBACK.md"
)

for rel in "${repo_required[@]}"; do
  if [[ ! -f "${REPO_ROOT}/${rel}" ]]; then
    echo "MISSING_REPO_REFERENCE ${rel}" >&2
    exit 1
  fi
  echo "FOUND_REPO_REFERENCE ${rel}"
done

for marker in \
  "BUNDLE_VERIFY: passed" \
  "ENV_PREFLIGHT: passed_or_blocked" \
  "EXISTING_VECTOR: discovered" \
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
  "AUTOMATION_GATE: default_deny" \
  "OUTPUT_SANITIZED: yes"; do
  grep -q "${marker}" "WORK-AGENT-START-PROMPT.md" "GITLAB-TICKET.md" "evidence/EVIDENCE-TEMPLATE.md"
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
grep -q "VECTOR_SECRET_REFS_NAMES_ONLY" "prompts/01-preflight-env-tools.md"
grep -q "suppress_duplicates" "${REPO_ROOT}/observability/vector/manifests/01-vector-alertmanager-normalizer.yaml"
grep -q "accepted_events" "${REPO_ROOT}/observability/vector/manifests/01-vector-alertmanager-normalizer.yaml"
grep -q "readinessProbe" "${REPO_ROOT}/observability/vector/manifests/01-vector-alertmanager-normalizer.yaml"
grep -q "livenessProbe" "${REPO_ROOT}/observability/vector/manifests/01-vector-alertmanager-normalizer.yaml"
echo "PROMPT_CONTRACT_OK: yes"

if grep -RInE \
  '(Bearer[[:space:]]+[A-Za-z0-9._-]+|token=|password:|secret:|pkc-[A-Za-z0-9-]+|lkc-[A-Za-z0-9-]+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|10\.[0-9]{1,3}\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)' \
  --exclude='verify-bundle.sh' .; then
  echo "PUBLIC_SAFETY_HITS: review output above" >&2
  exit 1
fi
echo "PUBLIC_SAFE_SCAN_OK: yes"

echo "VECTOR_KAFKA_ROUTING_NORMALIZATION_BUNDLE_VERIFY: passed"
