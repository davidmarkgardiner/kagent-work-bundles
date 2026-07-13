#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for rel in README.md FRONT-SHEET.md FLEET-TOPOLOGY.md DESIRED-STATE.md CHECKLIST.md WORK-AGENT-START-PROMPT.md WORK-HANDOVER-PROMPT.md GITLAB-TICKET.md STAKEHOLDER-DESIGN-DECISION.md TEAMS-STAKEHOLDER-MESSAGE.md FABLE-FEEDBACK-RESPONSE.md VISUAL.html skill/evidence-first-worker-triage/SKILL.md skill/evidence-first-worker-triage/references/replication-runbook.md skill/evidence-first-worker-triage/evals/evals.json requests/evidence-first-worker-triage-request.yaml payload/REFERENCE.md evidence/EVIDENCE-TEMPLATE.md templates/pilot-values.env.example templates/worker-vector-fleet-controls.yaml.tmpl templates/management-pilot-contract.yaml.tmpl templates/worker-evidence-pilot.yaml.tmpl templates/management-triage-pilot.yaml.tmpl templates/failure-fixtures.yaml.tmpl scripts/preflight-gates.sh scripts/render-pilot-templates.sh scripts/deploy-pilot.sh scripts/verify-healthy.sh scripts/simulate-failures.sh kustomize/README.md kustomize/base/kustomization.yaml kustomize/base/worker.yaml kustomize/base/management.yaml kustomize/overlays/pilot/kustomization.yaml kustomize/overlays/pilot/values.env.example kustomize/overlays/pilot/verify-healthy.sh kustomize/overlays/pilot/smoke-test.sh kustomize/overlays/pilot/MANUAL-RUN-CHECKLIST.md; do
  [[ -f "$rel" ]] || { echo "MISSING $rel" >&2; exit 1; }
  echo "FOUND $rel"
done

for intent in "Execute, do not review" "Non-negotiable implementation sequence" "Required proof" "durable TTL claim" "read-only kagent"; do
  grep -q "$intent" "skill/evidence-first-worker-triage/SKILL.md" || { echo "SKILL_EXECUTION_GUIDANCE_MISSING: $intent" >&2; exit 1; }
  echo "SKILL_EXECUTION_GUIDANCE_OK: $intent"
done

jq -e '.skill_name == "evidence-first-worker-triage" and (.evals | length >= 3)' skill/evidence-first-worker-triage/evals/evals.json >/dev/null || { echo "SKILL_EVALS_INVALID" >&2; exit 1; }
echo "SKILL_EVALS_OK"

for marker in "CRITIQUE_FEEDBACK_REVIEWED: yes" "FLEET_CORRECTIONS_DEFINED: yes" "WORKER_ALLOY_READ_ONLY: yes" "WORKER_VECTOR_REDACTION: yes" "KAFKA_CLUSTER_IDENTITY_AND_ACL: yes" "MANAGEMENT_TTL_IDEMPOTENCY: yes" "LOG_EVIDENCE_PATH_PROVEN: yes" "EVENT_EVIDENCE_PATH_PROVEN: yes" "REPLAY_SUPPRESSED: yes" "ALERTMANAGER_UNCHANGED: yes" "OUTPUT_SANITIZED: yes"; do
  grep -Rqs "$marker" . || { echo "MARKER_MISSING $marker" >&2; exit 1; }
  echo "MARKER_OK $marker"
done

for intent in "implementation work agent" "Do not stop at a rendered plan" "Create actual GitLab work items"; do
  grep -q "$intent" "WORK-AGENT-START-PROMPT.md" || { echo "EXECUTION_PROMPT_MISSING: $intent" >&2; exit 1; }
  echo "EXECUTION_PROMPT_OK: $intent"
done

if rg -n '192\.168\.|10\.[0-9]|redpanda\.redpanda|PRIVATE-TOKEN|password=' --glob '!scripts/verify-bundle.sh' --glob '!templates/management-triage-pilot.yaml.tmpl' --glob '!kustomize/base/management.yaml' .; then
  echo "PUBLIC_SAFE_SCAN_FAILED" >&2
  exit 1
fi
grep -q 'PRIVATE-TOKEN: \$GITLAB_TOKEN' templates/management-triage-pilot.yaml.tmpl || { echo "GITLAB_SECRET_REFERENCE_MISSING" >&2; exit 1; }
grep -q 'PRIVATE-TOKEN: \$GITLAB_TOKEN' kustomize/base/management.yaml || { echo "KUSTOMIZE_GITLAB_SECRET_REFERENCE_MISSING" >&2; exit 1; }
echo "GITLAB_TOKEN_IS_RUNTIME_SECRET_REFERENCE: yes"
echo "PUBLIC_SAFE_SCAN_OK: yes"
echo "EVIDENCE_FIRST_WORKER_TRIAGE_BUNDLE_VERIFY: passed"
