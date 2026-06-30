#!/usr/bin/env bash
set -euo pipefail

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: missing required command: $1" >&2
    exit 1
  }
}

require curl
require jq

: "${GRAFANA_URL:?set GRAFANA_URL, for example http://127.0.0.1:13030}"
: "${GRAFANA_USER:?set GRAFANA_USER}"
: "${GRAFANA_PASSWORD:?set GRAFANA_PASSWORD}"

FOLDER_UID="${GRAFANA_FOLDER_UID:-kagent-chaos-gameday}"
FOLDER_TITLE="${GRAFANA_FOLDER_TITLE:-Kagent Chaos Gameday}"
RULE_GROUP="${GRAFANA_RULE_GROUP:-kagent-chaos-gameday}"
DATASOURCE_UID="${GRAFANA_PROMETHEUS_DATASOURCE_UID:-prometheus}"
CHAOS_TARGET_NAMESPACE="${CHAOS_TARGET_NAMESPACE:-kagent-chaos-test}"
ROUTE_LABEL="${GRAFANA_ROUTE_LABEL:-kagent-chaos-gameday}"
CREATE_PAUSED="${GRAFANA_CREATE_PAUSED:-false}"

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT
chmod 700 "$tmp_dir"

api() {
  local method="$1"
  local path="$2"
  local payload="${3:-}"
  local response="${tmp_dir}/response.json"
  local status

  if [[ -n "$payload" ]]; then
    status="$(
      curl -sS -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
        -o "$response" -w "%{http_code}" \
        -X "$method" "${GRAFANA_URL%/}${path}" \
        -H "Content-Type: application/json" \
        --data-binary "@${payload}"
    )"
  else
    status="$(
      curl -sS -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
        -o "$response" -w "%{http_code}" \
        -X "$method" "${GRAFANA_URL%/}${path}"
    )"
  fi

  case "$status" in
    200|201|202) cat "$response" ;;
    404) return 44 ;;
    *)
      echo "ERROR: Grafana API ${method} ${path} failed with HTTP ${status}" >&2
      jq -r '.message // .error // .' "$response" >&2 || cat "$response" >&2
      return 1
      ;;
  esac
}

ensure_folder() {
  local payload="${tmp_dir}/folder.json"

  if api GET "/api/folders/${FOLDER_UID}" >/dev/null 2>&1; then
    echo "GRAFANA_FOLDER: exists ${FOLDER_UID}"
    return
  fi

  jq -n \
    --arg uid "$FOLDER_UID" \
    --arg title "$FOLDER_TITLE" \
    '{uid: $uid, title: $title}' > "$payload"

  api POST "/api/folders" "$payload" >/dev/null
  echo "GRAFANA_FOLDER: created ${FOLDER_UID}"
}

rule_payload() {
  local uid="$1"
  local title="$2"
  local expr="$3"
  local alertname="$4"
  local route_domain="$5"
  local target_agent="$6"
  local scenario="$7"
  local summary="$8"
  local runbook="$9"

  jq -n \
    --arg uid "$uid" \
    --arg folderUID "$FOLDER_UID" \
    --arg ruleGroup "$RULE_GROUP" \
    --arg title "$title" \
    --arg datasourceUid "$DATASOURCE_UID" \
    --arg expr "$expr" \
    --arg alertname "$alertname" \
    --arg route "$ROUTE_LABEL" \
    --arg routeDomain "$route_domain" \
    --arg targetAgent "$target_agent" \
    --arg scenario "$scenario" \
    --arg summary "$summary" \
    --arg runbook "$runbook" \
    --argjson isPaused "$CREATE_PAUSED" \
    '{
      uid: $uid,
      folderUID: $folderUID,
      ruleGroup: $ruleGroup,
      title: $title,
      condition: "C",
      data: [
        {
          refId: "A",
          queryType: "",
          relativeTimeRange: {from: 300, to: 0},
          datasourceUid: $datasourceUid,
          model: {
            expr: $expr,
            intervalMs: 60000,
            maxDataPoints: 100,
            refId: "A"
          }
        },
        {
          refId: "B",
          queryType: "",
          relativeTimeRange: {from: 300, to: 0},
          datasourceUid: "__expr__",
          model: {
            expression: "A",
            intervalMs: 1000,
            maxDataPoints: 43200,
            reducer: "last",
            refId: "B",
            type: "reduce"
          }
        },
        {
          refId: "C",
          queryType: "",
          relativeTimeRange: {from: 300, to: 0},
          datasourceUid: "__expr__",
          model: {
            conditions: [{
              evaluator: {params: [0], type: "gt"},
              operator: {type: "and"},
              reducer: {params: [], type: "last"},
              type: "query"
            }],
            expression: "B",
            intervalMs: 1000,
            maxDataPoints: 43200,
            refId: "C",
            type: "threshold"
          }
        }
      ],
      noDataState: "OK",
      execErrState: "Error",
      for: "0s",
      keep_firing_for: "0s",
      annotations: {
        summary: $summary,
        runbook: $runbook
      },
      labels: {
        alertname: $alertname,
        severity: "warning",
        route_to: $route,
        route_domain: $routeDomain,
        target_agent: $targetAgent,
        chaos_scenario: $scenario
      },
      isPaused: $isPaused
    }'
}

upsert_rule() {
  local uid="$1"
  local payload="$2"

  if api GET "/api/v1/provisioning/alert-rules/${uid}" >/dev/null 2>&1; then
    api PUT "/api/v1/provisioning/alert-rules/${uid}" "$payload" >/dev/null
    echo "GRAFANA_ALERT_RULE: updated ${uid}"
  else
    api POST "/api/v1/provisioning/alert-rules" "$payload" >/dev/null
    echo "GRAFANA_ALERT_RULE: created ${uid}"
  fi
}

ensure_folder

declare -a rules=(
  "kagent-chaos-pod-restarts|Kagent Chaos - Pod Restart Spike|increase(kube_pod_container_status_restarts_total{namespace=\"${CHAOS_TARGET_NAMESPACE}\"}[5m]) > 0|KagentChaosPodRestartSpike|application|aks-sre-triage-agent|pod-restart|Pod restart spike in ${CHAOS_TARGET_NAMESPACE}|Inspect pod logs, describe output, recent events, rollout status, and resource pressure."
  "kagent-chaos-network-5xx|Kagent Chaos - Network 5xx Or Latency|sum(rate(nginx_ingress_controller_requests{namespace=\"${CHAOS_TARGET_NAMESPACE}\",status=~\"5..\"}[5m])) > 0|KagentChaosNetwork5xxOrLatency|networking|networking-triage-agent|network-5xx|Network or ingress failure detected for ${CHAOS_TARGET_NAMESPACE}|Check ingress, service endpoints, DNS, TLS, network policy, and controller logs."
  "kagent-chaos-cert-expiry|Kagent Chaos - Certificate Expiry|min(certmanager_certificate_expiration_timestamp_seconds{namespace=\"${CHAOS_TARGET_NAMESPACE}\"}) - time() < 604800|KagentChaosCertificateExpiry|platform|platform-ops-agent|certificate-expiry|Certificate expiry window reached in ${CHAOS_TARGET_NAMESPACE}|Check Certificate, CertificateRequest, Issuer, Secret, and cert-manager events."
  "kagent-chaos-policy-violation|Kagent Chaos - Policy Violation|increase(policy_report_result_total{namespace=\"${CHAOS_TARGET_NAMESPACE}\",result=\"fail\"}[5m]) > 0|KagentChaosPolicyViolation|security|security-hardening-agent|policy-violation|Policy violation detected in ${CHAOS_TARGET_NAMESPACE}|Check policy result, workload owner, image/advisory evidence, and remediation recommendation."
)

for rule in "${rules[@]}"; do
  IFS="|" read -r uid title expr alertname route_domain target_agent scenario summary runbook <<< "$rule"
  payload="${tmp_dir}/${uid}.json"
  rule_payload "$uid" "$title" "$expr" "$alertname" "$route_domain" "$target_agent" "$scenario" "$summary" "$runbook" > "$payload"
  upsert_rule "$uid" "$payload"
done

echo "GRAFANA_CHAOS_ALERT_RULES: created_or_updated"
echo "GRAFANA_FOLDER_UID: ${FOLDER_UID}"
echo "GRAFANA_RULE_GROUP: ${RULE_GROUP}"
echo "GRAFANA_ROUTE_LABEL: ${ROUTE_LABEL}"
echo "GRAFANA_CREATE_PAUSED: ${CREATE_PAUSED}"
echo "OUTPUT_SANITIZED: yes"
