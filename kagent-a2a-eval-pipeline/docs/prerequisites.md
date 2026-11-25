# Prerequisites and air-gap inventory

Nothing in this bundle needs the public internet at run time. Everything below must be in place, mirrored internally and pinned **by digest** before the work agent builds anything.
A value shown as `{{PLACEHOLDER}}` is filled in the work environment. Versions marked *verified* were run in the home lab; the rest were not.

## 1. Platform, assumed already installed and the same as the lab

| Component | Version | State |
|---|---|---|
| kagent controller and agents | 0.7.13 (`kagent.dev/v1alpha2`) | verified (Assay, Warden 1 run) |
| kagent 1.x with Substrate | 1.0.0-alpha17 with Substrate 0.6.0-alpha3 (`api.kagent.dev/v1alpha3`) | verified (Warden, Guard, ticket runs). **1.0.1 not run** |
| agentgateway | controller and data plane 0.11.1 (0.7.13 lab) | verified. The 1.x lab used its own gateway; check its version |
| kagent-tools (read-only Kubernetes MCP) | chart 0.3.0, digest `sha256:77933dc8a9206e8b9a2e90135aa29a069b26234a50cb046d13f9645f7af0f241` | verified, installed with `rbac.readOnly=true`, `tools.enabledTools={k8s}` |
| Model route | an OpenAI-compatible route through the gateway | verified with Kimi; the work model differs |
| Gateway API CRDs, a working CNI that enforces NetworkPolicy | cluster-specific | Cilium or Calico |

The controllers and the A2A behaviour are the same at work only if the versions above match. If they differ, re-capture one real receipt (step 4 of `WORK-AGENT-PROMPT.md`) and compare it with `tests/fixtures/`.

## 2. Images and artifacts to mirror

| Artifact | Pin | Used for |
|---|---|---|
| `python:3.12-slim` | digest at mirror time | the CI runner base (`Dockerfile`) and the `validate` job |
| `python:3.12-alpine` | digest at mirror time | Lookout's GitLab tool server (and, in the lab only, its mock GitLab). The code is mounted from a ConfigMap; nothing is installed at runtime |
| runner image built from `Dockerfile` | digest of your build, set as `EVAL_IMAGE` | every live CI job |
| kubectl `v1.31.4` binary | checksum at mirror time | inside the runner image (`Dockerfile`) |
| `PyYAML==6.0.2`, `mkdocs==1.6.1` | wheel hashes | runner image and the docs build |
| `busybox:1.36` | digest | the seeded-fault and decoy pods in `fixtures/cluster/` |
| `ghcr.io/kagent-dev/kagent/tools:0.3.0` and its chart | the chart digest above | the read-only tool server |
| kagent, agentgateway and Substrate chart images | enumerate (below) | the platform itself |
| Substrate worker image `ghcr.io/kagent-dev/substrate/ateworker-gvisor:v1.0.0` (1.x baseline in the lab profile) | digest | gVisor actors |
| Any skill or knowledge image a 1.x agent mounts | digest | an unreachable local registry made actors fail to restore in the lab |

**Enumerate chart images instead of trusting a list:** render each pinned chart and collect them:

```sh
helm template <release> <chart> --version <pin> -f <your-values> | rg -o 'image:\s*\S+' | sort -u
```

Record each image, its source and its digest. Re-tag into the internal registry and record the new path. The work agent must not pull from a public registry.

## 3. Must exist before the build

| # | Item | Why |
|---|---|---|
| 1 | Gateway route to the A2A endpoint with caller authentication, and a test token for the eval agents | Assay and Warden call agents only through the gateway |
| 2 | Read-only Kubernetes tool server and its exact tool names | They become each contract's `allowedTools` |
| 3 | An approved model route for the agents **and** for each evaluator, plus a **separate route and credential for the overseer and Guard** | Evaluators are agents too; the supervisor must not share a quota with what it supervises |
| 4 | GitLab project, protected runner tagged `kagent-eval`, protected masked variables `AGW_BASE_URL`, `AGW_TOKEN`, `EVAL_KUBECONFIG`, `EVAL_IMAGE` | `.gitlab-ci.yml` fails closed without them |
| 5 | Service account for `EVAL_KUBECONFIG` limited to `eval-*` namespaces | Assay seeds a fault in a throwaway namespace |
| 6 | Working DNS for the nodes and CoreDNS. Test it after every node restart | Kind and some node images regenerate resolver config on restart. Actors then hang silently with no error and no model call |
| 7 | The receiver that writes the GitLab issue, plus read access to read it back | Warden's ticket check |
| 8 | Monitoring for the Guard: Grafana, Alertmanager, Tempo metrics, a route into the agent system, **and a separate human-only paging route** | The loop is design-only without them |
| 8b | A narrow identity for `guard/enforce.py`: create, get, list and delete `agentgatewaypolicies` with the guard label, in the one policy namespace only | It is the only component that writes to the cluster |
| 9 | Decisions: where a first-try evaluator FAIL routes on 1.x; which signals may auto-block (the code applies directly only for the signals you allow, through `enforce.py`, and a person releases it); the never-block list; token baselines per agent | See `HUMAN-PREREQUISITES.md` |

## 4. Known environment traps (all seen in the lab)

- A model gateway with no log lines while a run hangs means DNS or egress, not the model.
- A 400 from the model is permanent: it needs smaller tool outputs, not a retry. Do not run a failing agent in a loop.
- Admission webhooks (Kyverno) that are down block every apply, including the tool-server registration.
- A host that shuts down nightly leaves the lab to be re-checked each morning.
