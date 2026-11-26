# Next steps after the 26 Nov 2026 work status report

This sheet answers the work agent's status report from 26 Nov 2026. It says what to do next, what only a person can do, and what "same as the home lab" means.

## Update: answer to the second status report (26 Nov 2026)

Stopping at Lookout and refusing to reuse the shared GitLab MCP was correct. Three corrections:

1. **Phase 1 (Warden) is not finished.** A healthy `PASS/no_action` proves only the happy path. Still to do:
   - a case where the evaluator **corrects** a bad worker answer;
   - the ticket step written **only after PASS**;
   - the negative tests;
   - receipts saved for each.
2. **Phase 3 (Guard detection) does not wait for Assay.** Run `guard/detect.py` now on the Phase 1 receipts.
   - Without `--inventory` the result is `degraded`. That is an accepted result for this gate.
   - Skip `propose.py --dry-run-server` until the dedicated dry-run identity (row 13) exists.
3. **Report your local edits.** List the local Warden and presentation changes behind the 4 refreshed checksums (453 tests here vs 443 in the bundle). Do this before the next `git pull`, so they can be merged into the bundle or dropped on purpose.

**Secrets:** never read Secrets with `kubectl get secret -o yaml` or `-o json`. To check that a Secret exists, use `kubectl get secret <name>` or `kubectl describe secret <name>`, which show key names only. Ask a person to clear any session logs that still hold the earlier base64 output.

**Lookout resumes** when a person confirms all of these:

- the Secret `lookout-gitlab-token` holds a project access token for the test project only (role Reporter, scope `api`, short expiry);
- `LOOKOUT_ALLOWED_PROJECTS` is set to that one project;
- the reviewer, advisory-only status and trial period are recorded.

Then run step 4 below.

**Order from here:** finish Phase 1, then Phase 3 detection, then Phase 6 (when the token is confirmed).

## Scope for now: everything outside Grafana

**This sheet overrides the Grafana part of Phase 0 in `WORK-AGENT-PROMPT.md`.** Grafana is out of scope for now. Do not install, repair or wait for Grafana, Loki, Tempo, Mimir or Alertmanager.

What the platform already gives you:

- a GitLab project and a token the agent may use;
- a model and ModelConfig that reach the model through agentgateway;
- a cluster with kagent and agentgateway running and connected.

That is enough for everything except Phase 4 (the Overseer's alert intake), which is deferred.

| Phase | Needs Grafana? | Status for now |
|---|---|---|
| 0. Readiness | No (Grafana rows skipped) | **Do**, reduced: see step 2 |
| 1. Warden | No | **Do** |
| 2. Assay | No (needs a CI runner) | **Do** when rows 5–7 are filled; skip until then |
| 3. Guard: detect and propose | No | **Do**, on receipts (see below) |
| 4. Overseer alert intake | **Yes**: something must fire an alert webhook | **Deferred** |
| 5. Direct blocking | No | **Do** only with written owner approval (rows 16–18) |
| 6. Lookout | No | **Do** |
| 7. Config review | No (needs its own sandbox cluster) | **Do** when rows 26–32 are filled; skip until then |

### Why Guard does not need Grafana

`guard/detect.py` reads files, not Grafana. It accepts:

- `a2a_capture` `*.run.json` and raw A2A receipts: Warden and Assay already write these;
- `warden.jsonl`;
- generic JSONL access logs;
- OTLP-JSON trace files (optional).

Feed it the receipts from Phase 1. Without a list of started tasks (`--inventory`, row 14) it cannot see a run that never finishes, so it reports `degraded`, never `clean`. That list can come from kagent's own task list or the gateway; it does not need Grafana.

### OpenTelemetry without Grafana (optional)

OTel does not need Grafana. Grafana and Tempo only store and show the traces. To feed traces to Guard without them:

1. Point kagent's OTLP trace exporter at an OpenTelemetry Collector (check the kagent Helm chart's `otel` tracing values for your version).
2. Give the Collector a `file` exporter in JSON format. It writes one OTLP-JSON document per line.
3. **Split that file before giving it to `detect.py`.** The detector reads a `.jsonl` file as access-log lines and would misread trace lines. Put each line in its own `.json` file:

   ```sh
   mkdir -p otel-split && i=0; while IFS= read -r l; do [ -n "$l" ] && i=$((i+1)) && printf '%s' "$l" > "otel-split/trace-$i.json"; done < traces.jsonl
   python guard/detect.py --events otel-split/*.json <receipts...> --inventory started.json
   ```

This step is optional. Receipts plus an inventory are enough for the Phase 3 gate. Add OTel only if a Collector is already allowed at work.

## What the work agent does next (in order)

| # | Action | Gate (stop and report) |
|---|---|---|
| 1 | Pull the latest `kagent-work-bundles` main and run `./verify-bundle.sh` | `BUNDLE_OK: yes`, 443 tests. The report's counts (28 + 131 + 111) suggest an older copy without config review |
| 2 | **Phase 0, reduced:** pinned versions; the model route answers; the agentgateway route answers with caller authentication; GitLab token reaches the project. Mark the Grafana rows "out of scope (26 Nov sheet)" | Readiness table, Grafana rows marked out of scope, everything else green |
| 3 | **Phase 1, Warden:** rerun the smoke now (do not rely on the old `PASS/no_action`), then the negative tests | Worker corrected by the evaluator; ticket only after PASS; negative tests pass; receipts saved |
| 4 | **Phase 6, Lookout:** one run on a sandbox MR (or `lookout/ci/run_local.py` if no runner) | One advisory note; rerun of the same commit gives `up_to_date` |
| 5 | **Phase 3, Guard (no enforcement):** run `detect.py` on the Phase 1 receipts, then `propose.py --dry-run-server` | `clean` on good runs, `forbidden_tool` on a bad one, `degraded` when the inventory is missing; proposal accepted by server dry-run, nothing applied |
| 6 | **Phase 2, Assay:** only once rows 5–7 and 12 are filled | Smoke, then pass^3 per case through the gateway; an unprotected-branch MR fails closed |
| 7 | **Phase 5, direct blocking:** only with rows 16–18 signed off | Applied, read back and released on a throwaway route; a real request proves the Deny |
| 8 | **Phase 7, config review:** only on the dedicated sandbox cluster (rows 26–32) | `deploy-config-review.sh` Ready; `negative-config-review.sh` 12/12; one note on a sandbox MR; no `lookout-mr-*` namespaces left |
| 9 | Browser and PDF checks of `presentation/` (any machine with Chrome) | Screenshots look right; the PDFs open |

Rules unchanged: one phase per "go"; stop at the first failure and read the receipt; never loop a failing agent; no secrets in email or git.

## What only a person can do

Row numbers refer to `HUMAN-PREREQUISITES.md`. Already covered: GitLab project and token, model and ModelConfig, cluster with kagent and agentgateway.

| Owner | Ask | Rows | Unblocks |
|---|---|---|---|
| Platform / Security | Confirm the GitLab token is least-privilege, sits in Secret `lookout-gitlab-token`, and set `LOOKOUT_ALLOWED_PROJECTS` | 21 | Phase 6 |
| Data classification owner | Confirm the model may read source code (and an approved Harness on kagent 1.x) | 23 | Phase 6 |
| Platform | Gateway caller authentication and a scoped test token; the read-only tool names | 2, 3 | Phases 1, 6 |
| Platform | Where to get started tasks (kagent task list or gateway) | 14 | Phase 3 `clean` instead of `degraded` |
| Platform / Security | A dedicated identity for `propose.py --dry-run-server` | 13 | Phase 3 |
| Platform / DevEx | Protected runner tagged `kagent-eval`, CI variables, restricted `eval-*` account, mirrored runner image | 5, 6, 7, 24 | Phase 2 |
| Product owner | Written approval of auto-block signals and the never-block list | 16 | Phase 5 |
| Platform / Security | Narrow identity for `enforce.py`; JWT test caller and throwaway route | 17, 18 | Phase 5 |
| Platform | Dedicated sanitised sandbox cluster with the same versions, internal-only load balancers, Kubernetes 1.30+, an admin to install the fences once, kro plurals, mirrored PyYAML | 26–31 | Phase 7 |
| Product owner | Who reads the notes; how long advisory-only; where a first FAIL routes; who owns a failing agent | 9, 10, 25, 32 | People acting on the results |
| *Later* | Grafana 9+ (or an existing Alertmanager) with a webhook contact point to `guard/alert_receiver.py` | 11, 15, 19, 20 | Phase 4, deferred |

## Desired state: same as the home lab (minus Grafana)

Work is at lab parity, for now, when every line below has a saved receipt.

- [ ] `./verify-bundle.sh`: `BUNDLE_OK: yes`, 443 tests
- [ ] **Warden:** worker corrected by the evaluator; ticket written only after PASS; negative tests pass
- [ ] **Lookout:** advisory note on a sandbox MR; rerun gives `up_to_date`
- [ ] **Guard:** `detect.py` gives `clean`, `forbidden_tool` and `degraded` correctly on receipts; proposal accepted by server dry-run, nothing applied
- [ ] **Assay** (once a runner exists): healthy passes, rogue fails (exit 1), through the gateway in CI; unprotected-branch MR fails closed
- [ ] **Direct blocking** (once approved): gateway 200 → 403 → 200 on a throwaway route, with the ledger entry
- [ ] **Config review** (once the sandbox cluster exists): notes on sandbox MRs; 12/12 fence tests; no `lookout-mr-*` namespaces left
- [ ] **Demo:** `demo/run-demo.sh` scenes except the Grafana loop, ending with `reset` then `lights`: `guard blocks active: 0`
- [ ] Decks checked in a browser and as PDF
- [ ] *Deferred:* Overseer alert intake via Grafana or an Alertmanager webhook

Lab shortcuts not to copy at work: config review gets its own cluster; direct blocking needs written approval; secrets stay in approved stores.
