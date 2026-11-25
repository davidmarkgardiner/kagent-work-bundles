#!/usr/bin/env bash
# Offline integrity check for the Assay and Warden bundle. Needs no cluster and no credentials.
# Exit 0 only if every check passes. A skipped optional check is reported, never counted as a pass.
set -uo pipefail
cd "$(dirname "$0")"
fail=0; skipped=()
ok(){ printf 'PASS  %s\n' "$1"; }
bad(){ printf 'FAIL  %s\n' "$1"; fail=1; }

for f in FRONT-SHEET.md HUMAN-PREREQUISITES.md WORK-AGENT-PROMPT.md README.md EVALUATION-EXPLAINED.html mkdocs.yml \
         presentation/assay-warden-deck.html presentation/assay-warden-deck.pdf verify_completion.py a2a_capture.py score_and_gate.py \
         .gitlab-ci.yml completion-gate/contracts/sentinel-investigator.yaml evidence/LIVE-PROXMOX-2026-11-23.md \
         lookout/README.md lookout/lookout_review.py lookout/gitlab_review_mcp.py lookout/manifests/mr-security-review-agent.yaml lookout/manifests/mr-security-review-agent-v1alpha3.yaml lookout/manifests/lookout-gitlab-mcp.yaml lookout/ci/lookout.gitlab-ci.yml lookout/ci/run_local.py lookout/gateway/route-lookout.yaml lookout/lab/mock_gitlab.py lookout/lab/deploy-lab.sh lookout/DESIGN.md presentation/lookout-flow.html presentation/launch-deck.pdf docs/lookout.md docs/code-tour.md docs/presenter-card.md demo/show.py demo/show.sh evidence/LIVE-LOOKOUT-LAB-2026-11-25.md \
         REVIEW-HANDOVER.md PREREQUISITES-AIRGAP.md VARIABLES.md docs/guard.md guard/detect.py guard/propose.py guard/enforce.py guard/model_probe.py guard/alert_to_a2a.py guard/alert_receiver.py docs/grafana-alerting.md guard/alerts/grafana/alert-rules.yaml tests/fixtures/grafana-webhook-live.json guard/remediate.py docs/walkthrough.md guard/route_exporter.py demo/grafana-loop/up.sh demo/grafana-loop/down.sh demo/grafana-loop/provisioning/alerting/loop.yaml scorer/score-agent-run.py scorer/reporting.py presentation/launch-deck.html guard/fallbacks.example.yaml demo/run-demo.sh demo/ask_agent.py docs/demo.md tests/fixtures/a2a-v1x-demo-rogue-delete-live.json guard/circuit.py guard/loop-limits.yaml guard/rules.yaml evidence/GUARD-AND-LOOP-2026-11-24.md; do
  [[ -s "$f" ]] && ok "present: $f" || bad "missing or empty: $f"
done

python3 -m unittest discover -s tests >/tmp/assay-tests.log 2>&1 && ok "unit tests ($(grep -E '^Ran ' /tmp/assay-tests.log))" || { bad "unit tests"; tail -15 /tmp/assay-tests.log; }
python3 tests/lint_cases.py cases >/dev/null 2>&1 && ok "case lint" || bad "case lint"
python3 completion-gate/render_evaluator.py completion-gate/contracts/*.yaml 2>/dev/null | diff -q completion-gate/manifests/completion-evaluator-agent.yaml - >/dev/null \
  && ok "generated evaluator matches the contracts" || bad "generated evaluator is stale: run render_evaluator.py"
python3 - <<'PY' && ok "all YAML parses" || bad "YAML parse"
import sys, pathlib, yaml
for p in pathlib.Path('.').rglob('*.y*ml'):
    text = p.read_text()
    if '/out/' in str(p) or p.name == 'mkdocs.yml' or '{{' in text: continue   # templates with {{PLACEHOLDER}} are not valid YAML until filled
    list(yaml.safe_load_all(text))
PY

cmp -s PREREQUISITES-AIRGAP.md docs/prerequisites.md && cmp -s VARIABLES.md docs/variables.md && ok "docs copies match their sources" || bad "docs/prerequisites.md or docs/variables.md differs from the root file"

# Public-safety: private addresses, tokens and unresolved real hosts must not be in the bundle (the gitignored private handover is excluded).
pat='192\.168\.|(^|[^0-9.])10\.[0-9]+\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.|PRIVATE-TOKEN|password=|BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20}|sk-[A-Za-z0-9]{20}'
if command -v rg >/dev/null 2>&1; then
  hits=$(rg -n --no-messages -e "$pat" . --glob '!out/**' --glob '!LIVE-TEST-HANDOVER.md' --glob '!*.pdf' --glob '!SHA256SUMS' --glob '!verify-bundle.sh' | head -5)
else
  hits=$(grep -rnE "$pat" . --exclude-dir=out --exclude=LIVE-TEST-HANDOVER.md --exclude='*.pdf' --exclude=SHA256SUMS --exclude=verify-bundle.sh | head -5)
fi
[[ -z "$hits" ]] && ok "no private addresses or tokens" || { bad "private-looking content found"; echo "$hits"; }

if python3 -c 'import mkdocs' >/dev/null 2>&1; then
  python3 -m mkdocs build --strict -q -d "$(mktemp -d)" >/dev/null 2>&1 && ok "mkdocs build --strict" || bad "mkdocs build --strict"
else skipped+=("mkdocs build (pip install -r requirements-docs.txt)"); fi

if [[ -f SHA256SUMS ]]; then
  (shasum -a 256 -c SHA256SUMS >/dev/null 2>&1 || sha256sum -c SHA256SUMS >/dev/null 2>&1) && ok "SHA256SUMS" || bad "SHA256SUMS (a listed file changed; regenerate if intended)"
else skipped+=("SHA256SUMS not present"); fi

for s in "${skipped[@]:-}"; do [[ -n "$s" ]] && echo "SKIP  $s"; done
[[ $fail -eq 0 ]] && echo "BUNDLE_OK: yes" || echo "BUNDLE_OK: no"
exit $fail
