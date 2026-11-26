# Next steps after the 26 Nov 2026 work status report

This sheet answers the work agent's status report from 26 Nov 2026. It covers three things: where the work stands, what the agent does next, and what only a person can do. It ends with the target: the same state the home lab reached.

## 1. Where the work stands

| Helper | Home lab (proven) | Work (reported 26 Nov) | Gap |
|---|---|---|---|
| **Warden** (in-place A2A eval) | Worker corrected by the evaluator; ticket written only after PASS; negative tests pass | Worker and evaluator Ready; an earlier smoke gave `PASS/no_action` but was not rerun | Phase 1 gate not yet evidenced: rerun with receipts |
| **Assay** (pipeline eval) | Healthy case passes, rogue case fails (exit 1) | 28 offline tests pass | Runner, identity, image and CI variables missing (rows 5–7, 12) |
| **Guard** (detect, propose) | `detect.py` clean / `forbidden_tool` / `degraded`; proposal accepted by server dry-run | Offline tests pass | Waiting for observability (Phase 0) and rows 13–14 |
| **Overseer** (LGTM, alert intake) | Broken agent fixed by switching to the approved fallback model; Grafana alert loop end to end | Offline tests pass; 2 observability agents not Ready | Telemetry and alert path absent (Phase 0); rows 11, 15, 19, 20 |
| **Guard direct blocking** | Gateway 200 → 403 → 200 on a throwaway route | Not started (correct) | Rows 16–18; written owner approval |
| **Lookout** (MR security review) | Advisory note posted; rerun of the same commit gives `up_to_date` | 131 offline tests pass | Rows 21–25 (token, sandbox project, approved model, runner or local replay, owners) |
| **Lookout config review** | 4 MRs reviewed in a sandbox, notes posted, 12/12 fence tests, nothing left behind | Correctly not started | Rows 26–32 (dedicated sanitised sandbox cluster) |

**Read this first:** the report treats observability as blocking everything. It does not. Per `docs/rollout.md`:

- **Phase 1 (Warden)** needs no monitoring and no CI.
- **Phase 6 (Lookout)** and **Phase 7 (config review)** are independent of Phases 1–5.

Only Guard (Phase 3), the Overseer (Phase 4) and direct blocking (Phase 5) wait on observability. Three tracks can move now.

**Check the bundle version.** The report's test counts (28 + 131 + 111) do not add up to the current bundle's 443. Pull `kagent-work-bundles` main (`202665b` or later) and run `./verify-bundle.sh`. It must print `BUNDLE_OK: yes` with 443 tests. The config review mode (Phase 7, 45 tests) was added on 26 Nov and may be missing from the copy at work.

## 2. What the work agent does next (in order)

| # | Action | Gate (stop and report) |
|---|---|---|
| 1 | Pull the latest bundle and run `./verify-bundle.sh` | `BUNDLE_OK: yes`, 443 tests |
| 2 | **Phase 1, Warden:** rerun the smoke now (do not rely on the old result), then the negative tests | Worker corrected by the evaluator; ticket only after PASS; negative tests pass; receipts saved |
| 3 | **Phase 6, Lookout:** once rows 21–25 are filled, one run on the sandbox MR (or `lookout/ci/run_local.py` if there is no runner) | One advisory note; rerun of the same commit gives `up_to_date` |
| 4 | **Phase 0, again:** once the platform owner names the telemetry and alert path, redo the readiness table | Recent trace and log per application; a controlled test alert reaches the webhook; both observability agents Ready |
| 5 | **Phase 2, Assay:** once rows 5–7 and 12 are filled | Smoke, then pass^3 per case through the gateway; an unprotected-branch MR fails closed |
| 6 | **Phase 3, Guard (no enforcement):** after step 4 is green and rows 13–14 are filled | Clean / `forbidden_tool` / `degraded` as expected; proposal accepted by dry-run, nothing applied |
| 7 | **Phase 4, Overseer:** after Phase 3 and rows 11, 15, 19, 20 | One bounded overseer run, then one real alert end to end |
| 8 | **Phase 5, direct blocking:** only with rows 16–18 signed off | Applied, read back and released on a throwaway route; a real request proves the Deny |
| 9 | **Phase 7, config review:** only on the dedicated sandbox cluster (rows 26–32) | `deploy-config-review.sh` Ready; `negative-config-review.sh` 12/12; one note on a sandbox MR; no `lookout-mr-*` namespaces left |
| 10 | Browser and PDF visual checks of `presentation/` (any machine with Chrome; no cluster needed) | Screenshots look right; the PDFs open |

Rules unchanged: one phase per "go"; stop at the first failure and read the receipt; never loop a failing agent; no secrets in email or git.

## 3. What only a person can do

Grouped by who to ask. Row numbers refer to `HUMAN-PREREQUISITES.md`.

**Unblocks the most:**

| Owner | Ask | Rows | Unblocks |
|---|---|---|---|
| Platform / Observability | Name the approved telemetry and alert path (Grafana or an approved alternative that meets the Phase 0 gate). Confirm applications send traces and logs. Send one controlled test alert | 0, 15 | Phases 3, 4, 5 |
| Platform / Security | Least-privilege GitLab token into Secret `lookout-gitlab-token`; `LOOKOUT_ALLOWED_PROJECTS` list | 21 | Phases 6, 7 |
| DevEx | Sandbox GitLab project with a throwaway MR | 22 | Phases 6, 7 |
| Data classification owner | Approve a model that may read source code; ModelConfig (and Harness on 1.x) | 23 | Phases 6, 7 |

**Then:**

| Owner | Ask | Rows | Unblocks |
|---|---|---|---|
| Platform / DevEx | Protected runner tagged `kagent-eval`; masked CI variables; restricted `eval-*` service account; runner image pinned by digest and mirrored | 5, 6, 7, 24 | Phase 2 (and Lookout CI) |
| Agent owner | Review the first full run of each Assay case | 12 | Phase 2 |
| Platform / Security | Dry-run RBAC identity; start inventory source | 13, 14 | Phase 3 |
| Platform | Separate model route for the overseer and Guard; overseer read RBAC; approved fallbacks | 11, 19, 20 | Phase 4 |
| Product owner | Written approval of which signals may auto-block and the never-block list | 16 | Phase 5 |
| Platform / Security | Narrow identity for `enforce.py`; JWT test caller and throwaway route | 17, 18 | Phase 5 |
| Platform | Dedicated sanitised sandbox cluster, same versions, internal-only load balancers, Kubernetes 1.30+, admin to install the fences once, kro plurals, PyYAML mirrored | 26–31 | Phase 7 |
| Product owner | Who reads Lookout and config-review notes; how long advisory-only; where a first FAIL routes; who owns a failing agent | 9, 10, 25, 32 | Turning the helpers into a gate people read |

## 4. Desired state: same as the home lab

Work is "at lab parity" when every line below has a saved receipt.

- [ ] `./verify-bundle.sh`: `BUNDLE_OK: yes`, 443 tests
- [ ] **Warden:** worker corrected by the evaluator; ticket written only after PASS; negative tests pass
- [ ] **Assay:** healthy case passes, rogue case fails (exit 1), through the gateway, in CI; unprotected-branch MR fails closed
- [ ] **Telemetry:** recent trace and log per application; test alert reaches the receiver; observability agents Ready
- [ ] **Guard:** `detect.py` gives clean, `forbidden_tool` and `degraded` correctly; proposal accepted by server dry-run, nothing applied
- [ ] **Overseer:** a broken agent fixed by switching to an approved fallback; one real alert handled end to end
- [ ] **Direct blocking:** gateway 200 → 403 → 200 on a throwaway route, with the ledger entry
- [ ] **Lookout:** advisory note on a sandbox MR; rerun gives `up_to_date`
- [ ] **Config review:** notes on sandbox MRs (clean, write-tool risk, kro breakage); 12/12 fence tests; no `lookout-mr-*` namespaces left
- [ ] **Demo:** `demo/run-demo.sh` scenes run in order (`docs/walkthrough.md`), ending with `reset` then `lights`: `guard blocks active: 0`
- [ ] Presentation decks checked in a browser and as PDF

Parity does **not** mean copying the lab's shortcuts. At work, keep these differences:

- config review gets its own cluster;
- direct blocking needs written approval;
- secrets live only in approved stores.
