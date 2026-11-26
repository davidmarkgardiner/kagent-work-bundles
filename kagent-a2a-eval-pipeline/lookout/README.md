# Lookout: advisory security review on every merge request

When a merge request is opened or updated, a GitLab CI job asks a kagent agent on the cluster for a quick security review. The agent reads the MR through GitLab MCP and leaves **one note** on it. A human then reviews with that extra input. Lookout never approves or merges, and its CI job never blocks the pipeline.

It sits beside Assay (tests an agent before it ships) and Warden (signs off each run). It reuses their A2A call, error handling and unique-contextId logic from `a2a_capture.py`; nothing in Assay or Warden changed.

```
MR pipeline job  ->  A2A pointer {project, mr_iid, head_sha}  ->  agentgateway  ->  agent mr-security-review
                                                                                     |  lookout_get_mr / _diff / _file
                                                                                     |  lookout_post_note  (one note, updated in place)
CI job reads the A2A tool trajectory and only reports "posted" if a note really was posted.
```

## Files

| File | Role |
|---|---|
| `lookout_review.py` | CI client. Sends the pointer, classifies `posted` / `no_note` / `agent_error` / `infra_error`, writes `lookout-run.json`. Advisory: exits 0 unless `--strict`. |
| `gitlab_review_mcp.py` | The eight-tool GitLab MCP the agent uses: read the MR and its diff, read only the delta since the last review, read the previous review note, read files, browse and search the repo at the reviewed commit, and post the one note. Stdlib only, runs from a ConfigMap. Safety lives here (see below). |
| `manifests/mr-security-review-agent.yaml` | Agent for kagent 0.7.x (`kagent.dev/v1alpha2`). |
| `manifests/mr-security-review-agent-v1alpha3.yaml` | Same agent for kagent 1.x (`api.kagent.dev/v1alpha3`). A test keeps the two prompts identical. |
| `manifests/lookout-gitlab-mcp.yaml` | Deployment, Service and RemoteMCPServer for the shim. Token comes from a Secret you create. |
| `ci/lookout.gitlab-ci.yml` | Job template other projects `include:`. |
| `ci/run_local.py` | Replays the CI job on your own machine: reads the template's `rules:` and `script:`, sets the same `CI_*` variables, runs `lookout_review.py`. No runner, no exposed endpoint. |
| `gateway/route-lookout.yaml` | HTTPRoute + policy reaching only `mr-security-review`. |
| `DESIGN.md` | The design and decisions, with an **As built** section listing every change found by testing. Read it for the why. |
| `lab/` | **Lab only**: mock GitLab, its manifest, and `deploy-lab.sh`. Never deploy to a work cluster. |

## Safety design

- **The shim, not the prompt, limits what the agent can do.** Its code has GET calls and note create/update only. There is no approve, merge, push, branch or file-write call to be tricked into. A test fails if one appears.
- **Project allowlist.** `LOOKOUT_ALLOWED_PROJECTS` (exact paths or `group/*`); empty refuses everything.
- **MR content is untrusted.** The prompt says so; the lab run with an injection attempt in the MR description was reported as a finding, not obeyed.
- **Pinned to a commit.** The diff tool errors if the MR head moved. The note tool refuses to post for a non-current head, so an older pipeline can never overwrite a newer review.
- **One note, updated in place.** Marked `<!-- mr-security-review -->`; the shim only updates a marker note written by its own token user, so a commenter cannot hijack it. The CI job uses a per-MR `resource_group` so two runs cannot race into duplicates.
- **Note body is neutralised.** Image syntax, raw HTML and `@mentions` are stripped from the model's text (closes an exfiltration and notification-spam path).
- **Exact commits.** Any short sha the agent sends is resolved to the full 40 characters through GitLab's commits API before use, so every read is pinned exactly. A rejected sha gets an error that says how long it was and how to fix it (a model copying a long hex string is a real failure mode).
- **Clean note header.** The shim writes the marker and header itself and strips any copy the agent carries over from the previous note, so a note never shows a duplicated header.
- **"Completed" is not "posted".** The client checks the A2A trajectory for a successful `lookout_post_note` with the right project, MR and sha.

## Review modes and cheap retries (incremental review is OFF)

The agent starts every run by reading the previous review note (`lookout_get_review_state`) and picks a mode. The client records the mode in `lookout-run.json`.

| Mode | When | What it reads |
|---|---|---|
| `up_to_date` | the note already covers this exact commit (a retried job, a re-run) | the MR and the note only; posts nothing |
| `full` | anything else: no previous review, or a previous review of an older commit | the whole MR diff; the new note replaces the old one completely |
| ~~`incremental`~~ | **switched off** | the agent has no delta tool |

- **Why incremental is off.** In a lab run on a 1,000-line MR, the incremental note kept only the new finding and said the other two "remain as previously reported", but the note is overwritten in place, so they were lost. The prompt asked the agent to carry them forward and it did not. So the agent is not given `lookout_get_delta_diff` at all (the shim still serves it, for a future fix). With it off, the same scenario produced one note holding all three current findings.
- **To turn it back on safely**, findings must be made structured (file, severity, title, status) with the shim refusing a post that omits a previous open finding unless it is marked resolved. Not built.
- **Retries are idempotent.** Re-running a job for the same commit costs about 7k tokens and posts nothing. After an `infra_error` re-running is safe and cheap.
- `up_to_date` is **agent-attested**: the client accepts it only if the agent read the review state and posted nothing, but it can't check GitLab itself. The note's own commit sha makes a wrong claim visible.
- **Cost of the safe choice:** after a push, a full review of a 1,000-line MR is about 40k input tokens, against about 25k for the (defective) incremental review.

## Config review mode: test agent and gateway YAML in a sandbox before merge

For merge requests that change **kagent** objects (Agent, ModelConfig, RemoteMCPServer, MCPServer, AgentTemplate),
**kro** ResourceGraphDefinitions that wrap them (and their instances), or **agentgateway** objects (Gateway, HTTPRoute,
AgentgatewayPolicy, AgentgatewayBackend), reading the diff is not enough: the question is what the change does on the
cluster, and `main` rolls out to every cluster. A second agent, `mr-config-review`, answers that before merge:

```
MR job -> A2A pointer {project, mr_iid, head_sha} -> agent mr-config-review
            lookout_get_mr
            lookout_config_review   server fetches the YAML (base and head) from GitLab, then in code:
                                    static checks -> two sandbox namespaces (main vs MR) -> probes -> diff -> findings
            lookout_post_note       one note; refused unless it cites every high finding (CR-n)
```

The model never supplies YAML and never decides a finding; it explains them. The sandbox copy forces every object into
a `lookout-mr-*` namespace, refuses Secrets, RBAC, cluster-scoped kinds, BYO images, `ipBlock` NetworkPolicies and
references to other namespaces, neutralises kro Jobs, renders kro agents as stand-ins (no agent ever runs), only
dry-runs kagent objects, and lists every rewrite in the note as "not tested". Two admission policies fence the
ServiceAccount and kro's children to `lookout-mr-*`; a janitor CronJob removes anything a crashed run leaves.

| File | Role |
|---|---|
| `CONFIG-REVIEW-DESIGN.md` | Design, review-gate outcome and as-built notes. Read first |
| `config_review/engine.py` | Deterministic rules: scope, static checks, sandbox copy (rewrites and refusals), probe diff |
| `config_review/sandbox.py` | One run: fetch from GitLab, blast radius (read-only), set up both sides, probe, diff, tear down |
| `config_review/kube.py` | Minimal Kubernetes REST client (stdlib) |
| `config_review/janitor.py` | Removes expired sandbox namespaces, RGDs and generated CRDs (run by the CronJob) |
| `config_review_mcp.py` | The three-tool MCP server; enforces "cite every high finding" |
| `manifests/config-review-sandbox.yaml` | ServiceAccount, ClusterRole (no Secrets), two ValidatingAdmissionPolicies, Deployment, Service, RemoteMCPServer |
| `manifests/mr-config-review-agent-v1alpha3.yaml` | The agent (kagent 1.x) |
| `manifests/mr-config-review-agent.yaml` | The same agent for kagent 0.7.x / 0.9 (`kagent.dev/v1alpha2`; offline-validated against the 0.9.12 schema) |
| `config_review/fixtures/platform-config-mrs.json` | Mock GitLab project `lab/platform-config`: main plus MRs 21-24 (good, bad, kro valid, kro broken) |
| `lab/deploy-config-review.sh`, `lab/negative-config-review.sh` | Lab deploy, and live negative tests of the admission fences |

CI: the same client with `--review config --agent mr-config-review` (`lookout_review.py`). Status: lab-proven on
2026-11-26, see `evidence/LIVE-CONFIG-REVIEW-LAB-2026-11-26.md`. Not yet run against a real GitLab, from a real runner,
or on a separate sandbox cluster.

## Which kagent version

| kagent | Agent manifest | A2A call | Status |
|---|---|---|---|
| 0.7.x and **0.9** | `manifests/mr-security-review-agent.yaml` (`kagent.dev/v1alpha2`) | `--protocol 0.7`, path `/api/a2a/<ns>/<agent>/` | 0.9: manifests validated offline against the 0.9.12 CRD schemas; the client's 0.x path is unit-tested; **not run on a 0.9 cluster**. 0.7.13 was never run with Lookout. |
| 1.x | `manifests/mr-security-review-agent-v1alpha3.yaml` (needs a Harness) | `--protocol 1x`, path `/agents/<ns>/<agent>` | run live on 1.0.0-alpha17 |

Move to 1.0 later by switching to the v1alpha3 manifest and `--protocol 1x`; the tool server and the prompt are the same.

## Deploy

1. **Token Secret** (a person types it; never commit it). Use a project or group token with the least scope that can read the MR and post notes:
   `read -rs T; kubectl -n kagent create secret generic lookout-gitlab-token --from-literal=token="$T"; unset T`
2. **Shim code** (one source of truth): `kubectl -n kagent create configmap lookout-gitlab-mcp --from-file=server.py=gitlab_review_mcp.py`
3. Fill `{{GITLAB_URL}}` and `{{LOOKOUT_ALLOWED_PROJECTS}}` in `manifests/lookout-gitlab-mcp.yaml`, then apply it. **On kagent 1.x** change its RemoteMCPServer `apiVersion` to `api.kagent.dev/v1alpha3`.
4. Fill `{{MODEL_CONFIG}}` (and on 1.x `{{APPROVED_HARNESS}}`) and apply the matching agent manifest. Wait for `Ready`; check the RemoteMCPServer discovered exactly eight tools.
5. Apply `gateway/route-lookout.yaml` (override the Gateway name). On 1.x the A2A path is `/agents/<ns>/<agent>`, so set `AGW_A2A_PROTOCOL=1x`.
6. Set CI variables `AGW_BASE_URL` and `AGW_TOKEN` (masked), put `lookout_review.py` and `a2a_capture.py` in the runner image, and add the `include:`.

Lookout is advisory first. Read the notes for a while, tune the prompt, and only then think about a gate.

## CI: best effort

The GitLab MCP path is the part that was tested. The CI job template is written but **not run on a real GitLab runner**. A hosted runner can only call the agent if the gateway is reachable from it, which means exposing an endpoint; that is a deployment decision, so it is left open.

Ways to get the same behaviour without a runner:

1. **`ci/run_local.py` (recommended, tested offline).** Evaluates the template's own rules (draft/WIP skip, disabled switch, merge-request pipelines only), then runs the same script:
   `python lookout/ci/run_local.py --project group/proj --mr-iid 5 -- --base-url http://127.0.0.1:18083 --protocol 1x`
   It reads the MR head sha and title with `glab api`, or pass `--head-sha` and `--title` to skip GitLab. Run it on a machine that can reach the agent (a port-forward is enough).
2. **A self-hosted runner inside the network** that can reach the gateway. Register it, add the `include:`, and the template runs as written. This is the real test of the template.
3. **`gitlab-ci-local`** (optional, not tried here) runs a `.gitlab-ci.yml` locally in containers. It would exercise the YAML itself, but needs Docker and the merge-request variables set by hand.

Gitea is not recommended: Gitea Actions is a different pipeline format, so it would not test this template.

## Run locally

```sh
python -m unittest tests.test_lookout_mcp tests.test_lookout_client tests.test_lookout_manifests tests.test_lookout_e2e_local tests.test_lookout_local_ci -v
python lookout/lookout_review.py --base-url https://{{AGW_HOST}} --project group/proj --mr-iid 5 --head-sha <40-hex> [--protocol 1x] [--strict]
```

Exit: `0` advisory (or posted), `1` `--strict` and not posted, `2` bad input.

## Lab test (home lab only)

The quickest way to see it: `LOOKOUT_HARNESS=<harness> LOOKOUT_MODEL_CONFIG=<model-config> demo/run-demo.sh lookout` (about four minutes, mock GitLab, removes what it deploys; four checks). See the demo walkthrough, scene 9.


`lab/deploy-lab.sh` deploys the shim against a mock GitLab with three fixture MRs (planted vulnerabilities, a clean decoy, a prompt-injection attempt). Set `LOOKOUT_GITLAB_URL` and `LOOKOUT_PROJECTS` to point it at a real GitLab instead (create the `lookout-gitlab-token` Secret yourself first):

```sh
KUBE_CONTEXT=<lab-context> KAGENT_API=1x HARNESS=<harness> MODEL_CONFIG=<model-config> lookout/lab/deploy-lab.sh
KUBE_CONTEXT=<lab-context> lookout/lab/deploy-lab.sh down
```

Results and honest limits: [`../evidence/LIVE-LOOKOUT-LAB-2026-11-25.md`](../evidence/LIVE-LOOKOUT-LAB-2026-11-25.md). Short version: proven on kagent 1.0.0-alpha17 with GLM against a mock GitLab, and once against a real gitlab.com sandbox MR (posted, then updated in place); **not** proven from a real CI runner, through agentgateway, on kagent 0.7.x, or with a least-privilege token.

## Known limits

- Incremental review is switched off (see above), so every new commit is a full review. The agent has seven tools; the shim serves eight. A `full` review is always one force-push or one re-run of a new MR away.
- Findings vary between runs and `file:line` is often off by one. Treat the note as a lead for the human reviewer.
- The review reads the MR diff, plus files it chooses to fetch, list or search at the pinned commit through the GitLab API. It never clones the repo, runs nothing, and does not check dependency CVEs. Browsing the repo roughly doubled input tokens in the lab (about 10-13k to about 25k per review); the client warns above 20 tool calls (`--max-tool-calls`, default 20) but does not stop the agent.
- **Big MRs get a partial review, and the note says so.** The diff tool returns at most about 60,000 characters (roughly 1,500 lines) and omits whole files beyond that. It pages through up to 2,000 files, and reports `total_files`, `complete` and an `omitted_reasons` map (`size_cap`, `too_large_for_gitlab`, `collapsed_by_gitlab`, `empty_diff_binary_or_trimmed_by_gitlab`). An empty or trimmed diff is never counted as reviewed, and the note must open with "PARTIAL ... Reviewed X of Y files" when `complete` is false. GitLab's `generated_file` flag is deliberately ignored, because an MR can set it itself to hide code. In the lab, a 10,500-line / 150-file MR was reviewed as 30 of 150 files (see the evidence file). It is not a full review of a very large MR; use smaller MRs or add scanners.
- How GitLab's real API reports trimmed or too-large diffs has not been checked against a real large MR; the shim treats an empty diff for a modified file as omitted to be safe.
- Raw A2A receipts contain MR code. They are not CI artifacts; only `lookout-run.json` is.
